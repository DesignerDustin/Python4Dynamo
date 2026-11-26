# Dynamo is not Dead - Ep02: Rev Remove Sheets + Create Sheet Set

Revit 2027 / Dynamo 4.x, Python engine: PythonNet3.

Graph: Revisions - Remove From Sheets
- Remove Revisions from Sheets.py - the Remove Revisions from Sheets node. Removes the picked revisions from the sheets and reports any sheet where a revision cloud still holds the revision, with the steps to clear it.

Graph: Create Sheet Set By Revision On Sheet
- Sheets.Revisions.py - the Sheets.Revisions node. Returns the revisions on each sheet.
- ViewSet.ByViewsName.py - the ViewSet.ByViewsName node. Creates or updates the sheet set.

Update to the Ep01 graph (Revisions - Apply To Sheets)
- Sheet.AddRevisions_Revised.py - replaces Add Revisions to Sheets from [Ep01](../Ep01%20-%20Revisions%20Apply%20To%20Sheets). Skips revisions a sheet already has and reports the results as Markdown for an Interlude results form.
