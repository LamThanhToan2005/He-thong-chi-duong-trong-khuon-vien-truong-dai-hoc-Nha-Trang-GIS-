# -*- coding: utf-8 -*-
import arcpy
import re
import sys

# Cho phép ghi đè dữ liệu cũ
arcpy.env.overwriteOutput = True

if arcpy.CheckExtension("Network") == "Available":
    arcpy.CheckOutExtension("Network")
else:
    arcpy.AddError("Vui long bat extension Network Analyst!")
    sys.exit()

def dms_to_dd(dms_str):
    try:
        parts = re.findall(r"[-+]?\d*\.\d+|\d+", dms_str)
        if len(parts) == 1: return float(parts[0])
        d, m, s = float(parts[0]), float(parts[1]), float(parts[2])
        return d + (m / 60.0) + (s / 3600.0)
    except: return None

def main():
    try:
        # 1. NHẬN THAM SỐ
        x_str = arcpy.GetParameterAsText(0) 
        y_str = arcpy.GetParameterAsText(1) 
        target_name = arcpy.GetParameterAsText(2) 

        # 2. CẤU HÌNH ĐƯỜNG DẪN
        network_ds = r"D:\ALL(baitap)\ban do\he thong chi duong\NTU.gdb\Khuon_vien_NTU\Khuon_vien_NTU_ND2"
        building_points = r"D:\ALL(baitap)\ban do\he thong chi duong\NTU.gdb\Khuon_vien_NTU\Vi_Tri_Toa_Nha"
        
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]
        sr_wgs84 = arcpy.SpatialReference(4326)
        sr_layer = arcpy.Describe(building_points).spatialReference

        curr_x = dms_to_dd(x_str)
        curr_y = dms_to_dd(y_str)
        start_pt = arcpy.PointGeometry(arcpy.Point(curr_x, curr_y), sr_wgs84).projectAs(sr_layer)

        # 3. TÌM GIẢNG ĐƯỜNG GẦN NHẤT
        min_dist = float('inf')
        mid_stop_geom = None
        mid_stop_name = ""
        with arcpy.da.SearchCursor(building_points, ["SHAPE@", "Ten"]) as cursor:
            for shape, name in cursor:
                if name and name.upper().startswith("G"): 
                    d = start_pt.distanceTo(shape)
                    if d < min_dist:
                        min_dist = d
                        mid_stop_geom = shape
                        mid_stop_name = name

        # 4. LẤY TỌA ĐỘ ĐIỂM ĐÍCH
        end_stop_geom = None
        where_clause = "{} = '{}'".format(arcpy.AddFieldDelimiters(building_points, "Ten"), target_name)
        with arcpy.da.SearchCursor(building_points, ["SHAPE@"], where_clause) as cursor:
            for row in cursor: end_stop_geom = row[0]

        if not end_stop_geom:
            arcpy.AddError("Khong tim thay dich den: " + target_name)
            return

        # 5. GIẢI TOÁN TÌM ĐƯỜNG
        out_layer_name = "Route_To_" + target_name
        
        # Xóa lớp cũ trên bản đồ
        for lyr in arcpy.mapping.ListLayers(mxd, out_layer_name, df):
            arcpy.mapping.RemoveLayer(df, lyr)
        
        # XÓA DỮ LIỆU TẠM TRONG BỘ NHỚ (Khắc phục lỗi 000258)
        if arcpy.Exists("in_memory\\temp_pts"):
            arcpy.Delete_management("in_memory\\temp_pts")
        
        arcpy.AddMessage(">>> Dang tinh toan lo trinh...")
        
        route_res = arcpy.na.MakeRouteLayer(network_ds, out_layer_name, "Length")
        route_layer = route_res.getOutput(0)
        stops_class = arcpy.na.GetNAClassNames(route_layer)["Stops"]

        # Tạo Feature Class tạm
        temp_pts = arcpy.CreateFeatureclass_management("in_memory", "temp_pts", "POINT", spatial_reference=sr_layer)
        
        with arcpy.da.InsertCursor(temp_pts, ["SHAPE@"]) as icur:
            icur.insertRow([start_pt])
            icur.insertRow([mid_stop_geom])
            icur.insertRow([end_stop_geom])

        arcpy.na.AddLocations(route_layer, stops_class, temp_pts, "", "500 Meters")
        arcpy.na.Solve(route_layer)

        # 6. HIỂN THỊ
        arcpy.mapping.AddLayer(df, route_layer, "TOP")
        
        arcpy.AddMessage("---------------------------------------")
        arcpy.AddMessage("OK! Ket qua lo trinh:")
        arcpy.AddMessage("Diem trung gian (G): " + str(mid_stop_name))
        arcpy.AddMessage("Diem den: " + str(target_name))
        arcpy.AddMessage("---------------------------------------")

    except Exception as e:
        arcpy.AddError("Loi: " + str(e))
    finally:
        arcpy.CheckInExtension("Network")
        arcpy.RefreshActiveView()

if __name__ == "__main__":
    main()