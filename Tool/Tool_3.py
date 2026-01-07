# -*- coding: utf-8 -*-
import arcpy

def main():

    layer_name = "Toa_Nha_NTU"
    name_field = "Ten"

    search_name = arcpy.GetParameterAsText(0)

    arcpy.AddMessage("=== TÌM KIẾM TÒA NHÀ ===")
    arcpy.AddMessage("Tìm: {}".format(search_name))

    mxd = arcpy.mapping.MapDocument("CURRENT")
    df = arcpy.mapping.ListDataFrames(mxd)[0]

    layer = None
    for lyr in arcpy.mapping.ListLayers(mxd, "", df):
        if lyr.name == layer_name:
            layer = lyr
            break

    if layer is None:
        arcpy.AddError("Không tìm thấy layer: {}".format(layer_name))
        return

    where_clause = "{} = '{}'".format(
        arcpy.AddFieldDelimiters(layer, name_field),
        search_name.replace("'", "''")
    )

    arcpy.SelectLayerByAttribute_management(
        layer, "NEW_SELECTION", where_clause
    )

    count = int(arcpy.GetCount_management(layer).getOutput(0))

    if count == 0:
        arcpy.AddWarning("Không tìm thấy đối tượng")
        return

    arcpy.AddMessage("Đã tìm thấy {} đối tượng".format(count))

    # ZOOM + REFRESH (ĐÚNG)
    df.zoomToSelectedFeatures()
    arcpy.RefreshActiveView()
    arcpy.RefreshTOC()

if __name__ == "__main__":
    main()
