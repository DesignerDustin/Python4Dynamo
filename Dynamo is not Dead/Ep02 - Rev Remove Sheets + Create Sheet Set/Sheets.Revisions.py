# Sheets.Revisions  (per-sheet version)
# IN[0]  Sheets : sheet, list of sheets, or nested lists (wrapped, unwrapped,
#                 ElementId or int)
# OUT    One list of Revision elements per sheet, mirroring the input
#        structure. Uses GetAllRevisionIds (cloud-driven + manually added),
#        which Revit returns in sequence order.
#        Non-sheet views and nulls return an empty list so they drop out of
#        any downstream List.Contains / FilterByBoolMask.
# Read-only, so it is idempotent.

import clr
clr.AddReference("System")
clr.AddReference("RevitAPI")
clr.AddReference("RevitNodes")
clr.AddReference("RevitServices")

import System
from Autodesk.Revit.DB import ViewSheet, View, ElementId, Element
from Revit.Elements import ElementWrapper
from Revit.Elements import Element as DSElement
from RevitServices.Persistence import DocumentManager

doc = DocumentManager.Instance.CurrentDBDocument

bad_inputs = []
missing_revs = []
_wrapped = {}  # one wrapper per revision per run


def is_null(item):
    return item is None or type(item).__name__ == "StackValue"


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


def revisions_for(item):
    if is_null(item):
        return []
    elem = to_element(item)
    if elem is None:
        bad_inputs.append("{} (no element with that Id)".format(item))
        return []
    # ViewSheet derives from View, so test it first
    if isinstance(elem, ViewSheet):
        revs = []
        for rev_id in elem.GetAllRevisionIds():
            key = rev_id.Value
            if key not in _wrapped:
                rev = doc.GetElement(rev_id)
                if rev is None:
                    missing_revs.append(
                        "Sheet {} (ElementId {}) -> Revision ElementId {}".format(
                            elem.SheetNumber, elem.Id.Value, key))
                    continue
                # True = Revit-owned. False would let Dynamo delete the
                # revision when the wrapper is disposed on a later run.
                _wrapped[key] = ElementWrapper.ToDSType(rev, True)
            revs.append(_wrapped[key])
        return revs
    if isinstance(elem, View):
        return []
    elem_id = elem.Id.Value if isinstance(elem, Element) else "n/a"
    bad_inputs.append("{} (ElementId {})".format(type(elem).__name__, elem_id))
    return []


def walk(x):
    if isinstance(x, list):
        return [walk(i) for i in x]
    return revisions_for(x)


result = walk(IN[0])

if bad_inputs:
    raise TypeError("Expected ViewSheet or View, got:\n" + "\n".join(bad_inputs))
if missing_revs:
    raise ValueError("Sheets reference missing revisions:\n" + "\n".join(missing_revs))

OUT = result