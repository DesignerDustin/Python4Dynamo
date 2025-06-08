import clr

# Add references
clr.AddReference("RevitServices")
import RevitServices
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

# Get the current document
doc = DocumentManager.Instance.CurrentDBDocument

# Add Revit API reference
clr.AddReference("RevitAPI")
import Autodesk
from Autodesk.Revit.DB import *

# Add Revit Nodes reference
clr.AddReference("RevitNodes")
import Revit
clr.ImportExtensions(Revit.Elements)
clr.ImportExtensions(Revit.GeometryConversion)

# Get input
types = IN[0]

# Get family manager
FamilyMan = doc.FamilyManager

# Start transaction
TransactionManager.Instance.EnsureInTransaction(doc)

# Create new types (handle both single string and list of strings)
if isinstance(types, list):
    results = []
    for type_name in types:
        try:
            newtype = FamilyMan.NewType(type_name)
            results.append(newtype)
        except:
            results.append(f"Could not create type: {type_name}")
    newtype = results
else:
    # Handle single string
    try:
        newtype = FamilyMan.NewType(types)
    except:
        newtype = "Could not create new type"

# Complete the transaction
TransactionManager.Instance.TransactionTaskDone()

# Output
OUT = newtype
