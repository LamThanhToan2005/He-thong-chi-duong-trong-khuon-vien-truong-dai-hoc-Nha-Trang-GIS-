# -*- coding: utf-8 -*-
import arcpy
import sys
import re

def dms_to_dd(dms_str):
    """Chuyển đổi chuỗi 109 11 59 hoặc 109.1997 sang số thập phân"""
    try:
        # Tìm tất cả các cụm số trong chuỗi
        parts = re.findall(r"[-+]?\d*\.\d+|\d+", dms_str)
        
        if len(parts) == 0:
            return None
        if len(parts) == 1:
            return float(parts[0])
        
        # Nếu có 3 phần (Độ, Phút, Giây)
        d = float(parts[0])
        m = float(parts[1]) if len(parts) > 1 else 0.0
        s = float(parts[2]) if len(parts) > 2 else 0.0
        
        # Công thức: Decimal Degrees = D + M/60 + S/3600
        dd = d + (m / 60.0) + (s / 3600.0)
        return dd
    except:
        return None

def main():
    try:
        # ===== 1. NHẬN THAM SỐ CHUỖI =====
        x_input = arcpy.GetParameterAsText(0) # Ví dụ: 109 11 59
        y_input = arcpy.GetParameterAsText(1) # Ví dụ: 12 15 20

        val_x = dms_to_dd(x_input)
        val_y = dms_to_dd(y_input)

        if val_x is None or val_y is None:
            arcpy.AddError(u"Định dạng tọa độ không đúng. Hãy nhập kiểu: 109 11 59")
            return

        # ===== 2. CẤU HÌNH DỮ LIỆU =====
        layer_name = "Vi_Tri_Toa_Nha"
        name_field = "Ten"

        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]
        
        # Lấy Layer từ bản đồ
        layer = arcpy.mapping.ListLayers(mxd, layer_name)[0]
        sr_layer = arcpy.Describe(layer).spatialReference
        sr_wgs84 = arcpy.SpatialReference(4326) # Hệ tọa độ GPS chuẩn

        # Tạo điểm và chuyển về hệ tọa độ của Layer (để tính mét)
        pt = arcpy.PointGeometry(arcpy.Point(val_x, val_y), sr_wgs84)
        pt_projected = pt.projectAs(sr_layer)

        # ===== 3. TÌM VỊ TRÍ GẦN NHẤT =====
        min_dist = float('inf')
        nearest_name = ""
        nearest_oid = -1

        arcpy.AddMessage(u">>> Tọa độ thập phân: X={:.6f}, Y={:.6f}".format(val_x, val_y))

        with arcpy.da.SearchCursor(layer, ["OID@", "SHAPE@", name_field]) as cursor:
            for oid, shape, name in cursor:
                dist = pt_projected.distanceTo(shape)
                if dist < min_dist:
                    min_dist = dist
                    nearest_name = name
                    nearest_oid = oid

        # ===== 4. HIỂN THỊ =====
        if nearest_oid != -1:
            # Chọn và Zoom
            query = "{0} = {1}".format(arcpy.Describe(layer).OIDFieldName, nearest_oid)
            arcpy.SelectLayerByAttribute_management(layer, "NEW_SELECTION", query)
            df.zoomToSelectedFeatures()
            
            arcpy.AddMessage(u"📍 Kết quả:")
            arcpy.AddMessage(u"🏠 Tòa nhà: " + unicode(nearest_name))
            arcpy.AddMessage(u"📏 Khoảng cách: {:.2f} mét".format(min_dist))
        else:
            arcpy.AddWarning(u"Không tìm thấy dữ liệu.")

    except Exception as e:
        arcpy.AddError(u"Lỗi: " + str(e))

    arcpy.RefreshActiveView()

if __name__ == "__main__":
    main()