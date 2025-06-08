import clr
from Autodesk.DesignScript.Geometry import *

# Add Revit API references
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
clr.AddReference('RevitServices')

from Autodesk.Revit.DB import *
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

# Function to selectively convert values
def convert_values(input_list):
    if isinstance(input_list, list):
        result = []
        for item in input_list:
            if isinstance(item, list):
                result.append(convert_values(item))
            else:
                # Check if the value is already a decimal
                try:
                    # Convert to float first to check
                    float_val = float(item)
                    # If it's a whole number, convert to int
                    if float_val.is_integer():
                        result.append(int(float_val))
                    else:
                        # If it has decimal places, keep as float
                        result.append(float_val)
                except:
                    # If conversion fails, pass through unchanged
                    result.append(item)
        return result
    else:
        # Single value case
        try:
            float_val = float(input_list)
            if float_val.is_integer():
                return int(float_val)
            else:
                return float_val
        except:
            return input_list

# Get input from the node
input_values = IN[0]

# Convert values only where appropriate
OUT = convert_values(input_values)
