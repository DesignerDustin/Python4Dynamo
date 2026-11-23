"""
IN[0]  Sheets     : ViewSheet or list of ViewSheets (wrapped, unwrapped, or element IDs)
IN[1]  Revision   : Revision or list of Revisions (wrapped, unwrapped, or element IDs)
IN[2]  Run        : bool – nothing is modified when False

OUT    The input sheets, unchanged (scalar in -> scalar out, list in -> list out)
"""

import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")

from Autodesk.Revit.DB import ElementId, Revision, ViewSheet
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager
from System.Collections.Generic import List

doc = DocumentManager.Instance.CurrentDBDocument

# helpers

def to_list(value):
    """Normalise a scalar or list to a Python list. None -> empty list."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def resolve(item, expected_type, label):
    """Unwrap a Dynamo element / ElementId / int to a Revit element of expected_type.
    None passes through untouched."""
    if item is None:
        return None

    elem = UnwrapElement(item)

    if isinstance(elem, int):
        elem = doc.GetElement(ElementId(elem))
    elif isinstance(elem, ElementId):
        elem = doc.GetElement(elem)

    if elem is None:
        raise ValueError(f"{label}: could not resolve '{item}' to an element in the document.")

    if not isinstance(elem, expected_type):
        raise TypeError(
            f"{label}: expected {expected_type.__name__}, got "
            f"{type(elem).__name__} (Id {elem.Id.Value})."
        )
    return elem

# inputs

sheets = [resolve(s, ViewSheet, "Sheets") for s in to_list(IN[0])]
revisions = [resolve(r, Revision, "Revision") for r in to_list(IN[1])]
run = bool(IN[2]) if IN[2] is not None else False

revision_ids = [r.Id for r in revisions if r is not None]

# process

if run and sheets and revision_ids:
    errors = []

    TransactionManager.Instance.EnsureInTransaction(doc)

    for sheet in sheets:
        if sheet is None:
            continue
        try:
            current = sheet.GetAdditionalRevisionIds()
            existing_values = {eid.Value for eid in current}

            new_ids = List[ElementId](current)
            added = False
            for rid in revision_ids:
                if rid.Value not in existing_values:
                    new_ids.Add(rid)
                    existing_values.add(rid.Value)
                    added = True

            if added:
                sheet.SetAdditionalRevisionIds(new_ids)

        except Exception as ex:
            errors.append(
                f"Sheet '{sheet.SheetNumber}' (Id {sheet.Id.Value}): {ex}"
            )

    TransactionManager.Instance.TransactionTaskDone()

    if errors:
        raise Exception(
            f"{len(errors)} sheet(s) failed to receive revisions:\n" + "\n".join(errors)
        )

OUT = IN[0]