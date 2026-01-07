# -*- coding: utf-8 -*-
import arcpy
import os

class Toolbox(object):
    def __init__(self):
        self.label = "RouteFromNames Toolbox"
        self.alias = "routefromnames"
        self.tools = [RouteFromNames]

class RouteFromNames(object):
    def __init__(self):
        self.label = "Solve route by point names"
        self.description = "Chọn 2 tên điểm (start, stop) trong ViTri.shp, thêm làm Stops và solve route với Network Analyst."
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []

        # 0 Input point layer
        p0 = arcpy.Parameter(
            displayName="Input Points (feature layer or shapefile)",
            name="input_points",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
        params.append(p0)

        # 1 Name field
        p1 = arcpy.Parameter(
            displayName="Name Field",
            name="name_field",
            datatype="Field",
            parameterType="Required",
            direction="Input")
        p1.parameterDependencies = ["input_points"]
        params.append(p1)

        # 2 Network dataset
        p2 = arcpy.Parameter(
            displayName="Network Dataset (for routing)",
            name="network_dataset",
            datatype="DEFeatureClass",  # accepts dataset paths; change if needed
            parameterType="Required",
            direction="Input")
        params.append(p2)

        # 3 Start name (Value list populated dynamically)
        p3 = arcpy.Parameter(
            displayName="Start Point Name",
            name="start_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        p3.filter.type = "ValueList"
        params.append(p3)

        # 4 Stop name (Value list populated dynamically)
        p4 = arcpy.Parameter(
            displayName="Stop Point Name",
            name="stop_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        p4.filter.type = "ValueList"
        params.append(p4)

        # 5 Output route feature class
        p5 = arcpy.Parameter(
            displayName="Output Route Feature Class",
            name="out_route",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output")
        params.append(p5)

        return params

    def updateParameters(self, parameters):
        # Called when any parameter changes. We'll populate start/stop lists when input_points or name_field changes.
        try:
            input_points = parameters[0].value
            name_field_param = parameters[1].valueAsText

            if input_points and name_field_param:
                # attempt to get unique values
                names = []
                # if a layer, get its dataSource
                desc = arcpy.Describe(input_points)
                fc = desc.catalogPath if hasattr(desc, "catalogPath") else input_points

                # read unique values
                with arcpy.da.SearchCursor(fc, [name_field_param]) as cursor:
                    seen = set()
                    for row in cursor:
                        val = row[0]
                        if val is None:
                            continue
                        if val not in seen:
                            seen.add(val)
                            names.append(str(val))
                names.sort()

                # set the filter lists for start and stop params
                parameters[3].filter.list = names
                parameters[4].filter.list = names

                # if no default chosen, set first two (if available)
                if not parameters[3].value and len(names) >= 1:
                    parameters[3].value = names[0]
                if not parameters[4].value and len(names) >= 2:
                    parameters[4].value = names[1]
        except Exception:
            # silently ignore here; ArcGIS will show errors at execute if any
            pass

        return

    def updateMessages(self, parameters):
        # simple validation: start != stop
        if parameters[3].value and parameters[4].value:
            if parameters[3].value == parameters[4].value:
                parameters[4].setErrorMessage("Stop point must be different from Start point.")
        return

    def execute(self, parameters, messages):
        in_points = parameters[0].valueAsText
        name_field = parameters[1].valueAsText
        network = parameters[2].valueAsText
        start_name = parameters[3].valueAsText
        stop_name = parameters[4].valueAsText
        out_route = parameters[5].valueAsText

        arcpy.AddMessage("Input points: {}".format(in_points))
        arcpy.AddMessage("Name field: {}".format(name_field))
        arcpy.AddMessage("Start: {}, Stop: {}".format(start_name, stop_name))
        arcpy.AddMessage("Network dataset: {}".format(network))

        try:
            # make a temporary feature layer and select start & stop
            tmp_layer = "tmp_points_lyr"
            if arcpy.Exists(tmp_layer):
                arcpy.Delete_management(tmp_layer)
            arcpy.MakeFeatureLayer_management(in_points, tmp_layer)

            # build SQL - shapefile uses double quotes for fields, file geodatabase uses double quotes in arcpy too.
            # Use arcpy.AddFieldDelimiters for safety.
            delim = arcpy.AddFieldDelimiters(arcpy.Describe(in_points).path, name_field)
            expr_start = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(in_points, name_field), start_name.replace("'", "''"))
            expr_stop = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(in_points, name_field), stop_name.replace("'", "''"))

            # create separate layers for the two stops
            start_lyr = "start_lyr"
            stop_lyr = "stop_lyr"
            arcpy.MakeFeatureLayer_management(in_points, start_lyr, where_clause=expr_start)
            arcpy.MakeFeatureLayer_management(in_points, stop_lyr, where_clause=expr_stop)

            # Count to ensure selection found
            start_count = int(arcpy.GetCount_management(start_lyr).getOutput(0))
            stop_count = int(arcpy.GetCount_management(stop_lyr).getOutput(0))
            if start_count == 0:
                raise arcpy.ExecuteError("Không tìm thấy Start point: '{}'".format(start_name))
            if stop_count == 0:
                raise arcpy.ExecuteError("Không tìm thấy Stop point: '{}'".format(stop_name))

            arcpy.AddMessage("Found {} start point(s), {} stop point(s)".format(start_count, stop_count))

            # Create route layer
            route_layer_name = "RouteLayer"
            # default impedance; user can change by editing the code. Here we try "Length"
            result = arcpy.na.MakeRouteLayer(network, route_layer_name, impedance_attribute="Length")
            route_layer = result.getOutput(0)

            # get sublayer names
            sublayers = arcpy.na.GetNAClassNames(route_layer)
            stops_sublayer_name = sublayers["Stops"]

            # Add the two stops. Use a temporary feature class that merges the two selected features, or add them by order.
            # We'll add start first, then stop so route is from start->stop.
            arcpy.na.AddLocations(route_layer, stops_sublayer_name, start_lyr, field_mappings="Name Name", search_tolerance="5000 Meters", append="CLEAR")
            arcpy.na.AddLocations(route_layer, stops_sublayer_name, stop_lyr, field_mappings="Name Name", search_tolerance="5000 Meters", append="ADD")

            arcpy.AddMessage("Added stops to route.")

            # Solve
            arcpy.na.Solve(route_layer)
            arcpy.AddMessage("Route solved.")

            # Save routes sublayer to output
            # find routes sublayer name
            routes_sublayer = sublayers["Routes"]
            # get layer object for routes
            routes_layer = None
            for lyr in arcpy.mapping.ListLayers(route_layer):
                if lyr.name == routes_sublayer:
                    routes_layer = lyr
                    break

            # In ArcGIS Pro, arcpy.mapping may not list NA sublayers the same; safer to use arcpy.na.GetSolverOutput?
            # We'll export the Routes sublayer to out_route using CopyFeatures on the routes_sublayer name
            # Use arcpy.management.CopyFeatures with layer reference "RouteLayer\\Routes"
            route_layer_ref = route_layer + "\\" + routes_sublayer
            arcpy.management.CopyFeatures(route_layer_ref, out_route)
            arcpy.AddMessage("Saved route to: {}".format(out_route))

        except arcpy.ExecuteError:
            arcpy.AddError(arcpy.GetMessages(2))
            raise
        except Exception as e:
            arcpy.AddError("General error: {}".format(e))
            raise

        return
