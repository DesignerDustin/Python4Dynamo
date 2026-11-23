"""
Sheet.AddRevisions
Revit 2027 / Dynamo 4.x / PythonNet3 engine (.NET 10)

IN[0]  Sheets    : ViewSheet - single, list, or list of lists
                   (wrapped, unwrapped, ElementId, or int)
IN[1]  Revisions : Revision  - single, list, or list of lists
                   (wrapped, unwrapped, ElementId, or int)
IN[2]  Run       : bool - nothing is modified unless True (form wasSubmitted)

OUT    One Markdown string for Interlude's Layout.Markdown on a results form:
       a status line, the picked revisions, the sheets that got them, the
       sheets that already had them, and any sheet Revit would not update
       (with Revit's reason). Headings and bold labels are in capitals, the
       rest in normal case. Nothing picked or the form cancelled gives a one-
       line message.

Adds every revision to every sheet's "Revisions on Sheet" (additional
revision) list. A revision already in a sheet's list is skipped, and a sheet
whose list doesn't change is never written, so a second run changes nothing
(idempotent).

Sheets Revit refuses to update are collected and reported in the text after
the transaction closes, so every sheet that did update keeps its change. They
are not raised: a node error is invisible to someone running the graph from a
form. A wrong input type (a graph wiring mistake) still raises.
"""

import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")

from System.Collections.Generic import List
from Autodesk.Revit.DB import ElementId, Revision, ViewSheet
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

doc = DocumentManager.Instance.CurrentDBDocument


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def is_null(value):
    """None, or an unconnected / empty port (DesignScript StackValue)."""
    return value is None or type(value).__name__ == "StackValue"


def flatten(value):
    """Any nesting depth -> flat Python list. Nulls are dropped."""
    if is_null(value):
        return []
    if isinstance(value, (list, tuple)):
        flat = []
        for v in value:
            flat.extend(flatten(v))
        return flat
    return [value]


def resolve(item, expected_type, label):
    """Wrapped element / Revit element / ElementId / int -> Revit element."""
    elem = UnwrapElement(item)

    if isinstance(elem, bool):
        raise TypeError(f"{label}: got a bool ({elem}), expected {expected_type.__name__}.")
    if isinstance(elem, int):
        elem = doc.GetElement(ElementId(int(elem)))
    elif isinstance(elem, ElementId):
        elem = doc.GetElement(elem)

    if elem is None or not getattr(elem, "IsValidObject", False):
        raise ValueError(f"{label}: '{item}' is not a valid element in the active document.")

    if not isinstance(elem, expected_type):
        raise TypeError(
            f"{label}: expected {expected_type.__name__}, got "
            f"{type(elem).__name__} (Id {elem.Id.Value})."
        )
    return elem


def resolve_all(value, expected_type, label):
    """Flatten, resolve, and de-duplicate by element id (input order kept)."""
    seen, out = set(), []
    for item in flatten(value):
        elem = resolve(item, expected_type, label)
        if elem.Id.Value not in seen:
            seen.add(elem.Id.Value)
            out.append(elem)
    return out


def md(text):
    """Escape Interlude Markdown inline markers so names show as typed."""
    out = str(text)
    for ch in ("\\", "*", "_", "`", "["):
        out = out.replace(ch, "\\" + ch)
    return out


def sheet_label(sheet):
    return f"{sheet.SheetNumber} - {sheet.Name}"


def revision_label(rev):
    return f"Seq {rev.SequenceNumber} - {rev.Description} ({rev.RevisionDate})"


def run_flag(value):
    """True only when every supplied flag is True (and at least one exists)."""
    flags = flatten(value)
    return len(flags) > 0 and all(f is True for f in flags)


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------
if not run_flag(IN[2]):
    OUT = "Nothing was changed - the form was cancelled."
else:
    sheets = resolve_all(IN[0], ViewSheet, "Sheets")
    revisions = resolve_all(IN[1], Revision, "Revisions")

    if not sheets:
        OUT = "**NO SHEETS.** There were no sheets to add the revision(s) to, so nothing was changed."
    elif not revisions:
        OUT = "**NO REVISIONS PICKED.** Nothing was changed."
    else:
        added = []      # (sheet, [revisions added])
        had = []        # sheets that already had every revision
        failed = []     # (sheet, error text)

        TransactionManager.Instance.EnsureInTransaction(doc)
        try:
            for sheet in sheets:
                try:
                    current = list(sheet.GetAdditionalRevisionIds())
                    have = {eid.Value for eid in current}
                    missing = [r for r in revisions if r.Id.Value not in have]

                    if not missing:
                        had.append(sheet)
                        continue  # already has every revision - no write

                    new_ids = List[ElementId]()
                    for eid in current + [r.Id for r in missing]:
                        new_ids.Add(eid)

                    sheet.SetAdditionalRevisionIds(new_ids)
                    added.append((sheet, missing))

                except Exception as ex:
                    failed.append((sheet, str(ex)))
        finally:
            TransactionManager.Instance.TransactionTaskDone()

        by_number = lambda s: s.SheetNumber or ""
        added.sort(key=lambda p: by_number(p[0]))
        had.sort(key=by_number)
        failed.sort(key=lambda p: by_number(p[0]))

        if failed:
            status = (
                f"**NOT ALL SHEETS UPDATED.** {len(added)} of {len(sheets)} sheet(s) got the "
                f"revision(s); Revit would not update {len(failed)}."
            )
        elif added:
            status = f"**DONE.** Added the revision(s) to {len(added)} of {len(sheets)} sheet(s)."
        else:
            status = (
                f"**ALREADY UP TO DATE.** All {len(sheets)} sheet(s) already had the "
                "revision(s), so nothing was changed."
            )

        parts = [status, "**REVISIONS**\n" + "\n".join("- " + md(revision_label(r)) for r in revisions)]

        if added:
            many = len(revisions) > 1
            lines = []
            for sheet, revs in added:
                line = "- " + md(sheet_label(sheet))
                if many and len(revs) < len(revisions):
                    line += " (" + ", ".join(f"Seq {r.SequenceNumber}" for r in revs) + ")"
                lines.append(line)
            parts.append("**ADDED TO**\n" + "\n".join(lines))

        if had:
            parts.append("**ALREADY HAD THEM**\n" + "\n".join("- " + md(sheet_label(s)) for s in had))

        if failed:
            parts.append(
                "**REVIT WOULD NOT UPDATE THESE SHEETS**\n"
                + "\n".join(f"- {md(sheet_label(s))}: {md(err)}" for s, err in failed)
            )

        OUT = "\n\n".join(parts)