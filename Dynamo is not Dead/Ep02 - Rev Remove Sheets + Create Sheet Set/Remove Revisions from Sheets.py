"""
Sheet.RemoveRevisions  (Interlude results text)
Revit 2027 / Dynamo 4.x / PythonNet3 engine (.NET 10)

IN[0]  Sheets    : ViewSheet - single, list, or list of lists
                   (wrapped, unwrapped, ElementId, or int).
                   From Result.GetList(form, "SHEETS").
IN[1]  Revisions : Revision  - single, list, or list of lists
                   (wrapped, unwrapped, ElementId, or int).
                   From Result.GetList(form, "REVISIONS").
IN[2]  Run       : bool - nothing is modified unless True (form wasSubmitted)

OUT    One string of Markdown for Interlude's Layout.Markdown node on the
       results form. For every picked sheet that STILL shows a picked
       revision after the removal - because a revision cloud for it is on
       the sheet or in a view that shows on the sheet - it lists: the
       revision, Issued, where the cloud is (Held on sheet by), the sheet
       sets the sheet is in, other sheets the same cloud shows on, the
       cloud element Id(s), and numbered steps to remove it that name the
       view to open (no Select by ID needed). Sheets Revit refused to update
       get their own section. If nothing is left, one line says so.
       Headings and bold labels are in capitals; descriptions and steps are
       in normal case, which is easier to read in a long block of text.

       Interlude's Markdown has no tables, so each sheet gets a heading and
       a bullet list instead of a table row. User text is escaped so a * or
       _ in a sheet or view name is shown as typed.

How it works: a revision added through "Revisions on Sheet" is stored in
the sheet's additional revision list, and this node removes it from that
list. A revision that shows because of a cloud is not in that list - the
Revit API (and the Revisions on Sheet dialog) cannot remove it. Only
deleting the cloud or changing the cloud's Revision clears it.

Idempotent: a sheet is only written when its additional list actually holds
one of the revisions, so a second run changes nothing and reports the same
cloud-held sheets.
"""

import clr
clr.AddReference("System")
clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")

import System
from System.Collections.Generic import List
from Autodesk.Revit.DB import (
    ElementId, FilteredElementCollector, Revision, RevisionCloud,
    RevisionVisibility, ViewSheet, ViewSheetSet,
)
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


def to_id(value):
    """int -> ElementId."""
    return ElementId(int(value))


def resolve(item, expected_type, label):
    """Wrapped element / Revit element / ElementId / int -> Revit element."""
    elem = UnwrapElement(item)

    if isinstance(elem, bool):
        raise TypeError(f"{label}: got a bool ({elem}), expected {expected_type.__name__}.")
    if isinstance(elem, int):
        elem = doc.GetElement(to_id(elem))
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


def run_flag(value):
    """True only when every supplied flag is True (and at least one exists)."""
    flags = flatten(value)
    return len(flags) > 0 and all(f is True for f in flags)


def sheet_label(sheet):
    return f"{sheet.SheetNumber} - {sheet.Name}"


def revision_label(rev):
    return f"Seq {rev.SequenceNumber} - {rev.Description} ({rev.RevisionDate})"


def md(text):
    """Escape Interlude Markdown inline markers so names show as typed."""
    out = str(text)
    for ch in ("\\", "*", "_", "`", "["):
        out = out.replace(ch, "\\" + ch)
    return out


CLOUD_AND_TAG = int(RevisionVisibility.CloudAndTagVisible)


def how_to_remove(rev, owner, is_sheet, count, number, also_on):
    steps = []
    if rev.Issued:
        steps.append(
            "View > Sheet Issues/Revisions: clear Issued on this revision "
            "(Revit does not let you edit clouds of an issued revision)."
        )
    if int(rev.Visibility) != CLOUD_AND_TAG:
        steps.append(
            ("In the same dialog" if rev.Issued else "View > Sheet Issues/Revisions:")
            + " set Show to Cloud and Tag for this revision so the cloud is visible."
        )
    if count == 1:
        clouds, verb, tagged = "the revision cloud", "is", f" (revision number {number} on this sheet)" if number else ""
    else:
        clouds, verb, tagged = f"the {count} revision clouds", "are", f" (revision number {number} on this sheet)" if number else ""
    if is_sheet:
        steps.append(
            f"Open this sheet in the Project Browser. {clouds[0].upper() + clouds[1:]} for this "
            f"revision{tagged} {verb} drawn on the sheet itself, not inside a view."
        )
    else:
        name = f"'{md(owner.Name)}'" if owner is not None else "named in 'Held on sheet by'"
        steps.append(
            f"Open the view {name} in the Project Browser (the view itself, not the sheet): "
            f"{clouds} for this revision{tagged} {verb} drawn in that view."
        )
    steps.append(
        "Zoom to fit (ZF) to find the cloud(s) and click to select. If you can't see "
        "one, check Visibility/Graphics (VG) > Annotation Categories > Revision Clouds "
        "is on" + ("." if is_sheet else ", and turn off the crop region for a moment.")
    )
    steps.append(
        "Delete the cloud(s), or change their revision in their properties to "
        "a different revision."
    )
    if also_on:
        steps.append(
            "The same cloud also shows on the sheets listed under SAME CLOUD ALSO SHOWS ON, "
            "so deleting it can take the revision off those sheets too."
        )
    if rev.Issued:
        steps.append("Select Issued again for this revision.")
    return steps


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------
run = run_flag(IN[2])
sheets = resolve_all(IN[0], ViewSheet, "Sheets")
revisions = resolve_all(IN[1], Revision, "Revisions")

if not run:
    OUT = "Nothing was changed - the form was cancelled."
elif not sheets:
    OUT = "No sheets were selected - nothing was changed."
elif not revisions:
    OUT = "No revisions were selected - nothing was changed."
else:
    remove_values = {r.Id.Value for r in revisions}
    rev_by_value = {r.Id.Value: r for r in revisions}
    sheet_values = {s.Id.Value for s in sheets}

    # sheet -> sheet set names (for the Sheet sets column)
    sets_by_sheet = {}
    for vss in FilteredElementCollector(doc).OfClass(ViewSheetSet):
        for v in vss.Views:
            if isinstance(v, ViewSheet):
                sets_by_sheet.setdefault(v.Id.Value, []).append(vss.Name)

    # -----------------------------------------------------------------------
    # remove from the additional ("Revisions on Sheet") lists
    # -----------------------------------------------------------------------
    failed = {}

    TransactionManager.Instance.EnsureInTransaction(doc)
    try:
        changed = False
        for sheet in sheets:
            try:
                current = list(sheet.GetAdditionalRevisionIds())
                kept = [eid for eid in current if eid.Value not in remove_values]

                if len(kept) == len(current):
                    continue  # none of the revisions are in this sheet's list - no write

                # Build the .NET list item by item; do not pass a Python list
                # to the List[ElementId] constructor under PythonNet 3.
                new_ids = List[ElementId]()
                for eid in kept:
                    new_ids.Add(eid)

                sheet.SetAdditionalRevisionIds(new_ids)
                changed = True

            except Exception as ex:
                failed[sheet.Id.Value] = str(ex)

        if changed:
            doc.Regenerate()
    finally:
        TransactionManager.Instance.TransactionTaskDone()

    # -----------------------------------------------------------------------
    # clouds of the selected revisions:
    # (sheet id, revision id) -> {owner view id: [cloud ids]}
    # cloud id -> every sheet it shows on
    # -----------------------------------------------------------------------
    held = {}
    cloud_sheets = {}
    for cloud in FilteredElementCollector(doc).OfClass(RevisionCloud):
        rid = cloud.RevisionId.Value
        if rid not in remove_values:
            continue
        on_sheets = [sid.Value for sid in cloud.GetSheetIds()]
        cloud_sheets[cloud.Id.Value] = on_sheets
        for sid in on_sheets:
            if sid in sheet_values:
                held.setdefault((sid, rid), {}).setdefault(
                    cloud.OwnerViewId.Value, []
                ).append(cloud.Id.Value)

    sheet_number_cache = {}

    def sheet_number(value):
        if value not in sheet_number_cache:
            s = doc.GetElement(to_id(value))
            sheet_number_cache[value] = s.SheetNumber if isinstance(s, ViewSheet) else f"Id {value}"
        return sheet_number_cache[value]

    # -----------------------------------------------------------------------
    # what is still on each selected sheet
    # -----------------------------------------------------------------------
    rows = []       # (sequence, sheet number, Markdown block)
    refused = []    # Markdown bullets for sheets Revit would not update

    for sheet in sheets:
        sval = sheet.Id.Value
        sets_text = ", ".join(sorted(sets_by_sheet.get(sval, []))) or "-"

        if sval in failed:
            refused.append(
                f"- **{md(sheet_label(sheet))}** (sheet sets: {md(sets_text)}): "
                f"{md(failed[sval])}"
            )
            continue

        still = [eid.Value for eid in sheet.GetAllRevisionIds() if eid.Value in remove_values]
        for rid in still:
            rev = rev_by_value[rid]
            places = held.get((sval, rid))
            issued = "Yes" if rev.Issued else "No"

            if not places:
                rows.append((rev.SequenceNumber, sheet.SheetNumber, "\n".join([
                    f"### {md(sheet_label(sheet).upper())}",
                    f"- **REVISION:** {md(revision_label(rev))}",
                    f"- **ISSUED:** {issued}",
                    f"- **SHEET SETS:** {md(sets_text)}",
                    "",
                    "Still shown, but no revision cloud for it was found. Select the "
                    "sheet, then in Properties click Revisions on Sheet > Edit and clear "
                    "the revision there.",
                ])))
                continue

            for owner_value, cloud_list in sorted(places.items()):
                owner = doc.GetElement(to_id(owner_value))
                is_sheet = owner_value == sval

                if is_sheet:
                    where = "Cloud placed on the sheet"
                elif owner is not None:
                    where = f"Cloud in view '{owner.Name}'"
                else:
                    where = f"Cloud in view Id {owner_value}"

                try:
                    number = sheet.GetRevisionNumberOnSheet(to_id(rid)) or ""
                except Exception:
                    number = ""

                also = sorted(
                    {v for c in cloud_list for v in cloud_sheets.get(c, []) if v != sval},
                    key=sheet_number,
                )
                also_text = ", ".join(sheet_number(v) for v in also) or "-"
                ids_text = ", ".join(str(c) for c in sorted(cloud_list))
                steps = how_to_remove(rev, owner, is_sheet, len(cloud_list), number, also)

                rows.append((rev.SequenceNumber, sheet.SheetNumber, "\n".join(
                    [
                        f"### {md(sheet_label(sheet).upper())}",
                        f"- **REVISION:** {md(revision_label(rev))}",
                        f"- **ISSUED:** {issued}",
                        f"- **HELD ON SHEET BY:** {md(where)}",
                        f"- **SHEET SETS:** {md(sets_text)}",
                        f"- **SAME CLOUD ALSO SHOWS ON:** {md(also_text)}",
                        f"- **CLOUD IDS:** {ids_text} (Manage > Select by ID)",
                        "",
                        "**HOW TO REMOVE**",
                    ]
                    + [f"{i}. {step}" for i, step in enumerate(steps, 1)]
                )))

    rows.sort(key=lambda r: (r[0], r[1]))

    parts = []
    if rows:
        parts.append(
            f"**{len(rows)} STILL SHOWING.** These picked sheets still show a picked "
            "revision because a revision cloud for it is on the sheet or in a view on "
            "the sheet. Everything else was removed."
        )
        for r in rows:
            parts.append("---")
            parts.append(r[2])
    if refused:
        parts.append("---")
        parts.append(
            "### REVIT WOULD NOT UPDATE THESE SHEETS\n"
            "None of the picked revisions were removed from them.\n"
            + "\n".join(refused)
        )
    if not parts:
        parts.append(
            f"**DONE.** All {len(revisions)} picked revision(s) are off all "
            f"{len(sheets)} picked sheet(s)."
        )

    OUT = "\n\n".join(parts)