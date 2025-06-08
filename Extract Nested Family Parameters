# Import necessary libraries
import clr
from Autodesk.Revit.DB import *
import Autodesk.Revit.DB as DB
import RevitServices
from RevitServices.Persistence import DocumentManager

# Get the current document
doc = DocumentManager.Instance.CurrentDBDocument

# Unwrap input from Dynamo
# IN[0] should be a list of Revit.Elements.Parameter objects
parameters = UnwrapElement(IN[0])

# Define parameters to exclude
excluded_names = [
    "Assembly Code","Comments","Cost","Default Elevation","Description","Elevation from Level",
    "Export to IFC","Export to IFC As","Export Type to IFC","Export Type to IFC As",
    "Family","Family Type","Family and Type","IFC Predefined Type","IfcGUID","Image","Keynote","Label","Level",
    "Manufacturer","Mark","Model","Moves With Nearby Elements","Offset from Host","Schedule Level","System Name",
    "Type","Type Comments","Type IFC Predefined Type",
    "Type IfcGUID","Type Mark","URL","Visibility/Graphics Overrides","Visible"
]

# Filter parameters
def filter_parameters(param_list):
    filtered_parameters = []
    
    for param in param_list:
        # Check if the parameter is not read-only and not in the excluded list
        if not param.IsReadOnly and param.Name not in excluded_names:
            filtered_parameters.append(param)
    
    return filtered_parameters

# Process input parameters
if isinstance(parameters, list):
    result = filter_parameters(parameters)
else:
    # If it's a single parameter, convert to list first
    result = filter_parameters([parameters])

# Assign output
OUT = result
