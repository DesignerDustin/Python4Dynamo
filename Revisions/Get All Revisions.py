import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")

from Autodesk.Revit.DB import Revision
from RevitServices.Persistence import DocumentManager

doc = DocumentManager.Instance.CurrentDBDocument

OUT = [doc.GetElement(rid) for rid in Revision.GetAllRevisionIds(doc)]