# ViewSet.ByViewsName  (Revit 2027 / Dynamo 4.x / PythonNet3, Interlude results text)
# IN[0]  Views         : view, list, or nested lists (wrapped, unwrapped,
#                        ElementId or int)
# IN[1]  SetName       : string (first non-null item is used if a list)
# IN[2]  Overwrite_T-F : bool  (first non-null item is used if a list)
# IN[3]  Run_T-F       : bool  (first non-null item is used if a list).
#                        Anything other than true (false, null, cancelled
#                        form, unconnected port) returns a message and
#                        changes nothing.
# OUT    One Markdown string for Interlude's Layout.Markdown on a results
#        form: what happened (created / updated / already up to date / not
#        created and why) and the sheets in the set. Headings and bold
#        labels are in capitals, the rest in normal case.
#
#        Things a user can fix - the revision is on no sheet, a set with
#        that name already exists and Overwrite is off, Revit refused to
#        save - are reported in the text instead of raised, because a
#        node error is invisible to someone running the graph from a form.
#        Wrong input types (a graph wiring mistake) still raise.
#
# Idempotent: an existing set with the same name is updated in place
# (same ElementId); if it already holds exactly these views, nothing is
# written and no transaction is opened.

import clr
clr.AddReference("System")
clr.AddReference("RevitAPI")
clr.AddReference("RevitNodes")
clr.AddReference("RevitServices")

import System
from Autodesk.Revit.DB import (
    Element, ElementId, FilteredElementCollector, View, ViewSet,
    ViewSheetSet, PrintRange, SubTransaction
)
from Revit.Elements import Element as DSElement
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

doc = DocumentManager.Instance.CurrentDBDocument


def is_null(x):
    return x is None or type(x).__name__ == "StackValue"


def flatten(x):
    if isinstance(x, list):
        out = []
        for i in x:
            out.extend(flatten(i))
        return out
    return [x]


def first_value(x):
    for i in flatten(x):
        if not is_null(i):
            return i
    return None


def md(text):
    """Escape Interlude Markdown inline markers so names show as typed."""
    out = str(text)
    for ch in ("\\", "*", "_", "`", "["):
        out = out.replace(ch, "\\" + ch)
    return out


def view_label(v):
    num = getattr(v, "SheetNumber", None)
    return "{} - {}".format(num, v.Name) if num else v.Name


def view_list(views):
    return "\n".join("- " + md(view_label(v)) for v in views)


def to_element(item):
    """Accept wrapped, unwrapped, ElementId, or int. Pass None through."""
    if is_null(item):
        return None
    if isinstance(item, DSElement):
        return item.InternalElement
    if isinstance(item, Element):
        return item
    if isinstance(item, ElementId):
        return doc.GetElement(item)
    if isinstance(item, int) and not isinstance(item, bool):
        return doc.GetElement(ElementId(System.Int64(item)))
    return UnwrapElement(item)


run = first_value(IN[3]) if len(IN) > 3 else None

# ---- run switch: only an explicit true does anything ---------------------
if run is not True:
    OUT = "Nothing was changed - the form was cancelled."
else:
    # ---- views ----------------------------------------------------------
    views, seen, bad = [], set(), []
    for item in flatten(IN[0]):
        if is_null(item):
            continue
        elem = to_element(item)
        if elem is None:
            bad.append("{} (no element with that Id)".format(item))
            continue
        if not isinstance(elem, View):
            elem_id = elem.Id.Value if isinstance(elem, Element) else "n/a"
            bad.append("{} (ElementId {})".format(type(elem).__name__, elem_id))
            continue
        if elem.Id.Value not in seen:
            seen.add(elem.Id.Value)
            views.append(elem)
    if bad:
        raise TypeError("Expected View elements, got:\n" + "\n".join(bad))

    # ---- name / overwrite ---------------------------------------------
    name_in = first_value(IN[1])
    if name_in is None or not str(name_in).strip():
        raise ValueError("SetName is required.")
    set_name = str(name_in).strip()

    ow = first_value(IN[2])
    overwrite = bool(ow) if ow is not None else False

    # ---- printable only ------------------------------------------------
    printable, skipped = [], []
    for v in views:
        if v.IsTemplate or not v.CanBePrinted:
            skipped.append(v)
        else:
            printable.append(v)
    printable.sort(key=lambda v: (getattr(v, "SheetNumber", "") or "", v.Name))
    target_ids = set(v.Id.Value for v in printable)

    skipped_text = ""
    if skipped:
        skipped_text = (
            "\n\n**SKIPPED**\n"
            "These show the revision but can't go in a sheet set "
            "(placeholder or non-printable sheets):\n" + view_list(skipped)
        )

    if not printable:
        OUT = (
            "**NO SHEETS FOUND.** No printable sheet shows the revision {}, so no "
            "sheet set was created or changed.".format("'" + md(set_name) + "'")
            + skipped_text
        )
    else:
        # ---- existing set ------------------------------------------------
        existing = None
        for vss in FilteredElementCollector(doc).OfClass(ViewSheetSet):
            if vss.Name == set_name:
                existing = vss
                break

        status = None
        if existing is not None:
            current_ids = set(v.Id.Value for v in existing.Views)
            if current_ids == target_ids:
                status = "ALREADY UP TO DATE."
            elif not overwrite:
                status = "NOT CHANGED."

        error = None
        if status is None:
            view_set = ViewSet()
            for v in printable:
                view_set.Insert(v)

            TransactionManager.Instance.EnsureInTransaction(doc)
            sub = SubTransaction(doc)
            sub.Start()
            try:
                print_manager = doc.PrintManager
                print_manager.PrintRange = PrintRange.Select
                settings = print_manager.ViewSheetSetting
                if existing is not None:
                    # update in place: keeps the set's ElementId
                    settings.CurrentViewSheetSet = existing
                    settings.CurrentViewSheetSet.Views = view_set
                    ok = settings.Save()
                else:
                    # start from In-Session so whatever named set happens to be
                    # current is never modified
                    settings.CurrentViewSheetSet = settings.InSession
                    settings.CurrentViewSheetSet.Views = view_set
                    ok = settings.SaveAs(set_name)
                if not ok:
                    raise RuntimeError("Revit returned False from Save/SaveAs.")
                sub.Commit()
            except Exception as ex:
                if sub.HasStarted() and not sub.HasEnded():
                    sub.RollBack()
                error = ex
            finally:
                sub.Dispose()
                TransactionManager.Instance.TransactionTaskDone()

            if error is None:
                status = "UPDATED." if existing is not None else "CREATED."

        name = "'" + md(set_name) + "'"
        count = len(printable)
        if error is not None:
            OUT = (
                "**NOT SAVED.** Revit would not save the sheet set {}: {}".format(name, md(error))
                + skipped_text
            )
        elif status == "NOT CHANGED.":
            OUT = (
                "**NOT CHANGED.** A sheet set named {} already exists with different "
                "sheets, and OVERWRITE was set to NO. Run the graph again with OVERWRITE "
                "set to YES to replace its sheets with these {} sheet(s):\n\n{}".format(
                    name, count, view_list(printable))
                + skipped_text
            )
        else:
            OUT = (
                "**SHEET SET {}** {} holds these {} sheet(s):\n\n{}".format(
                    status, name, count, view_list(printable))
                + skipped_text
            )