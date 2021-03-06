# Copyright (c) 2016-2020, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.


import bpy
from bpy.props import *
from .error import *
from .utils import *

#-------------------------------------------------------------
#   Check if RNA is driven
#-------------------------------------------------------------

def isBoneDriven(rig, pb):
    return (getBoneDrivers(rig, pb) != [])


def getBoneDrivers(rig, pb):
    fcus = []
    if rig.animation_data:
        for channel in ["rotation_euler", "rotation_quaternion", "location", "scale"]:
            path = 'pose.bones["%s"].%s' % (pb.name, channel)
            fcus += [fcu for fcu in rig.animation_data.drivers if path == fcu.data_path]
    return fcus


def getDrivingBone(fcu, rig):
    for var in fcu.driver.variables:
        if var.type == 'TRANSFORMS':
            trg = var.targets[0]
            if trg.id == rig:
                return trg.bone_target
    return None


def isFaceBoneDriven(rig, pb):
    if isBoneDriven(rig, pb):
        return True
    else:
        par = pb.parent
        return (par and par.name[-3:] == "Drv" and isBoneDriven(rig, par))


def getShapekeyDriver(skeys, sname):
    return getRnaDriver(skeys, 'key_blocks["%s"].value' % (sname), None)


def getShapekeyPropDriver(skeys, sname):
    return getRnaDriver(skeys, 'key_blocks["%s"].value' % (sname), 'SINGLE_PROP')


def getRnaDriver(rna, path, type):
    if rna and rna.animation_data:
        for fcu in rna.animation_data.drivers:
            if path == fcu.data_path:
                if not type:
                    return fcu
                for var in fcu.driver.variables:
                    if var.type == type:
                        return fcu
    return None

#-------------------------------------------------------------
#   Classes for storing drivers
#-------------------------------------------------------------

class Driver:
    def __init__(self, fcu):
        drv = fcu.driver
        self.data_path = fcu.data_path
        self.array_index = fcu.array_index
        self.type = drv.type
        self.use_self = drv.use_self
        self.expression = drv.expression
        self.variables = []
        for var in drv.variables:
            self.variables.append(Variable(var))

    def create(self, rig, bname):
        pb = rig.pose.bones[bname]
        channel = self.data_path.rsplit(".")[-1]
        fcu = pb.driver_add(channel, self.array_index)
        drv = fcu.driver
        drv.type = self.type
        drv.use_self = self.use_self
        drv.expression = self.expression
        for var in self.variables:
            var.create(drv.variables.new())


class Variable:
    def __init__(self, var):
        self.type = var.type
        self.name = var.name
        self.target = Target(var.targets[0])

    def create(self, var):
        var.name = self.name
        var.type = self.type
        self.target.create(var.targets[0])


class Target:
    def __init__(self, trg):
        self.id = trg.id
        self.bone_target = trg.bone_target
        self.transform_type = trg.transform_type
        self.transform_space = trg.transform_space

    def create(self, trg):
        trg.id = self.id
        trg.bone_target = self.bone_target
        trg.transform_type = self.transform_type
        trg.transform_space = self.transform_space

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def makeDriver(name, rna, channel, idx, attr, factor, rig):
    fcurves = rna.driver_add(channel)
    fcu = fcurves[idx]
    fcu.driver.type = 'SCRIPTED'

    string = "%.4f" % (factor*attr.value)
    string = "0"
    for n,drv in enumerate(attr.drivers.values()):
        string += " + %.4f*x%d" % (factor*drv[1], n+1)
    fcu.driver.expression = string

    for n,drv in enumerate(attr.drivers.values()):
        asset = drv[0].asset
        addDriverVar(fcu, "x%d" % (n+1), asset.name, rig)

#-------------------------------------------------------------
#   Bone drivers
#-------------------------------------------------------------

def varnames():
    return ["A", "B", "C"]


def makeDriverString(vec):
    string = "("
    first = True
    vars = []
    for j,comp in enumerate(varnames()):
        x = int(1000*vec[j])
        if x != 0:
            if first:
                string += ("%d*%s" % (x, comp))
                first = False
            else:
                if x > 0:
                    string += ("+%d*%s" % (x, comp))
                else:
                    string += ("%d*%s" % (x, comp))
            vars.append((j,comp))
    if vars:
        return (string + ")*1e-3"), vars
    else:
        return "", []


def makeSimpleBoneDriver(vec, rna, channel, rig, ob, bname, idx):
    string,vars = makeDriverString(vec)
    if string:
        makeBoneDriver(string, vars, rna, channel, rig, ob, bname, idx)


def makeProductBoneDriver(vecs, rna, channel, rig, ob, bname, idx):
    string = ""
    for vec in vecs:
        string1,vars = makeDriverString(vec)
        if string1:
            string += ("*min(1,max(0,%s))" % string1)
    if string:
        makeBoneDriver(string[1:], vars, rna, channel, rig, ob, bname, idx)


def makeSplineBoneDriver(uvec, points, rna, channel, rig, ob, bname, idx):
    n = len(points)
    xi,yi = points[0]
    string = "[%s if x< %s" % (getPrint(yi), getPrint(xi))
    vars = []
    for i in range(1, n):
        xj,yj = points[i]
        kij = (yj-yi)/(xj-xi)
        zs,zi = getSign(yi - kij*xi)
        string += (" else %s*x%s%s if x< %s " %
            (getPrint(kij), zs, getPrint(zi), getPrint(xj)))
        xi,yi = xj,yj
    string += " else %s for x in [" % getPrint(yj)
    for i,comp in enumerate(["A","B","C"]):
        us,ui = getSign(uvec[i])
        string += "%s%s*%s" % (us, getPrint(ui), comp)
        vars.append((i,comp))
    string += "]][0]     "
    if len(string) > 254:
        msg = "String driver too long:\n"
        for n in range(5):
            msg += "%s         \n" % (string[30*n, 30*(n+1)])
        raise DazError(msg)

    makeBoneDriver(string, vars, rna, channel, rig, ob, bname, idx)


def getPrint(x):
    string = "%4f" % x
    while (string[-1] == "0"):
        string = string[:-1]
    return string[:-1] if string[-1] == "." else string


def getSign(u):
    if u < 0:
        return "-", -u
    else:
        return "+", u


def makeBoneDriver(string, vars, rna, channel, rig, ob, bname, idx):
    rna.driver_remove(channel, idx)
    fcu = rna.driver_add(channel, idx)
    fcu.driver.type = 'SCRIPTED'
    fcu.driver.expression = string
    ttypes = ["ROT_X", "ROT_Y", "ROT_Z"]
    for j,vname in vars:
        addTransformVar(fcu, vname, ttypes[j], rig, bname)
    return fcu


def addTransformVar(fcu, vname, ttype, rig, bname):
    var = fcu.driver.variables.new()
    var.type = 'TRANSFORMS'
    var.name = vname
    trg = var.targets[0]
    trg.id = rig
    trg.bone_target = bname
    trg.transform_type = ttype
    trg.transform_space = 'LOCAL_SPACE'


def driverHasVar(fcu, vname):
    for var in fcu.driver.variables:
        if var.name == vname:
            return True
    return False


def clearBendDrivers(fcus):
    for fcu in fcus:
        if fcu.array_index != 1:
            fcu.driver.expression = "0"
            for var in fcu.driver.variables:
                fcu.driver.variables.remove(var)


def copyDriver(fcu1, rna2, id=None):
    channel = fcu1.data_path.rsplit(".",2)[-1]
    if channel == "value":
        idx = -1
    else:
        idx = fcu1.array_index
    words = fcu1.data_path.split('"')
    if (words[0] == "pose.bones[" and
        hasattr(rna2, "pose")):
        rna2 = rna2.pose.bones[words[1]]
    fcu2 = rna2.driver_add(channel, idx)
    fcu2.driver.type = fcu1.driver.type
    if hasattr(fcu1.driver, "use_self"):
        fcu2.driver.use_self = fcu1.driver.use_self
    fcu2.driver.expression = fcu1.driver.expression
    for var1 in fcu1.driver.variables:
        var2 = fcu2.driver.variables.new()
        var2.type = var1.type
        var2.name = var1.name
        trg1 = var1.targets[0]
        trg2 = var2.targets[0]
        if id:
            trg2.id = id
        else:
            trg2.id = trg1.id
        trg2.bone_target = trg1.bone_target
        trg2.data_path = trg1.data_path
        trg2.transform_type = trg1.transform_type
        trg2.transform_space = trg1.transform_space
    return fcu2


def changeDriverTarget(fcu, id):
    for var in fcu.driver.variables:
        targ = var.targets[0]
        targ.id = id


def removeDriverBoneSuffix(fcu, suffix):
    n = len(suffix)
    for var in fcu.driver.variables:
        for trg in var.targets:
            if trg.bone_target[-n:] == suffix:
                trg.bone_target = trg.bone_target[:-n]

#-------------------------------------------------------------
#   Prop drivers
#-------------------------------------------------------------

def makePropDriver(prop, rna, channel, rig, expr, idx=-1):
    rna.driver_remove(channel, idx)
    fcu = rna.driver_add(channel, idx)
    fcu.driver.type = 'SCRIPTED'
    fcu.driver.expression = expr
    addDriverVar(fcu, "x", prop, rig)


def makeShapekeyDriver(ob, sname, value, rig, prop, min=None, max=None):
    setFloatProp(rig, prop, value, min=min, max=max)
    skey = ob.data.shape_keys.key_blocks[sname]
    if getShapekeyDriver(ob.data.shape_keys, sname):
        skey.driver_remove("value")
    fcu = skey.driver_add("value")
    fcu.driver.type = 'SCRIPTED'
    fcu.driver.expression = "x"
    addDriverVar(fcu, "x", prop, rig)


def addVarToDriver(fcu, rig, prop, factor):
    if hasDriverVar(fcu, prop, rig):
        print("Already", prop)
        return
    varnames = getAllDriverVars(fcu)
    n = ord("A")
    while chr(n) in varnames:
        n += 1
    vname = chr(n)
    string = fcu.driver.expression
    fcu.driver.expression = string + ("+%.4f*%s" % (factor, vname))
    addDriverVar(fcu, vname, prop, rig)

#-------------------------------------------------------------
#   Access to properties.
#   Don't know whether to use custom attributes or custom props with RNA_UI
#-------------------------------------------------------------

def truncateProp(prop):
    if len(prop) > 63:
        print('Truncate property "%s"' % prop)
        return prop[:63]
    else:
        return prop


def setFloatProp(ob, prop, value, min=None, max=None):
    value = float(value)
    min = float(min) if min is not None and GS.useDazPropLimits else GS.propMin
    max = float(max) if max is not None and GS.useDazPropLimits else GS.propMax
    prop = truncateProp(prop)
    ob[prop] = value
    rna_ui = ob.get('_RNA_UI')
    if rna_ui is None:
        rna_ui = ob['_RNA_UI'] = {}
    rna_ui[prop] = { "min": min, "max": max, "soft_min": min, "soft_max": max}
    if hasattr(ob, "property_overridable_library_set"):
        ob.property_overridable_library_set('["%s"]' % prop, True)


def setBoolProp(ob, prop, value, desc=""):
    prop = truncateProp(prop)
    ob[prop] = value
    rna_ui = ob.get('_RNA_UI')
    if rna_ui is None:
        rna_ui = ob['_RNA_UI'] = {}
    rna_ui[prop] = { "min": 0, "max": 1 }
    setattr(bpy.types.Object, prop,
        BoolProperty(default=value, description=desc))
    setattr(ob, prop, value)
    ob[prop] = value
    if hasattr(ob, "property_overridable_library_set"):
        ob.property_overridable_library_set('["%s"]' % prop, True)

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def addDriverVar(fcu, vname, dname, rig):
    var = fcu.driver.variables.new()
    var.name = vname
    var.type = 'SINGLE_PROP'
    trg = var.targets[0]
    trg.id_type = 'OBJECT'
    trg.id = rig
    trg.data_path = '["%s"]' % dname
    return trg


def hasDriverVar(fcu, dname, rig):
    path = '["%s"]' % dname
    for var in fcu.driver.variables:
        trg = var.targets[0]
        if trg.id == rig and trg.data_path == path:
            return True
    return False


def getAllDriverVars(fcu):
    return [var.name for var in fcu.driver.variables]


def replaceDriverBone(assoc, rna, path, idx=-1):
    for fcu in rna.animation_data.drivers:
        if (path == fcu.data_path and
            (idx == -1 or idx == fcu.array_index)):
            changeBoneTarget(fcu, assoc)


def changeBoneTarget(fcu, assoc):
    for var in fcu.driver.variables:
        if var.type == 'TRANSFORMS':
            for trg in var.targets:
                trg.bone_target = newBoneTarget(trg.bone_target, assoc)


def newBoneTarget(bname, assoc):
    for mhx,daz in assoc:
        if daz == bname:
            return mhx
    return bname


def checkDriverBone(rig, rna, path, idx=-1):
    for fcu in rna.animation_data.drivers:
        if (path == fcu.data_path and
            (idx == -1 or idx == fcu.array_index)):
            for var in fcu.driver.variables:
                if var.type == 'TRANSFORMS':
                    for trg in var.targets:
                        if trg.bone_target not in rig.data.bones.keys():
                            pass
                            #print("  ", trg.bone_target)


def getShapekeyDrivers(ob, drivers={}):
    if (ob.data.shape_keys is None or
        ob.data.shape_keys.animation_data is None):
        #print(ob, ob.data.shape_keys, ob.data.shape_keys.animation_data)
        return drivers

    for fcu in ob.data.shape_keys.animation_data.drivers:
        words = fcu.data_path.split('"')
        if (words[0] == "key_blocks[" and
            len(words) == 3 and
            words[2] == "].value"):
            drivers[words[1]] = fcu

    return drivers


def copyShapeKeyDrivers(ob, drivers):
    skeys = ob.data.shape_keys
    for sname,fcu in drivers.items():
        if (getShapekeyDriver(skeys, sname) or
            sname not in skeys.key_blocks.keys()):
            continue
        skey = skeys.key_blocks[sname]
        copyDriver(fcu, skey)


def isNumber(string):
    try:
        float(string)
        return True
    except ValueError:
        return False


def getAllBoneDrivers(rig, bones):
    if rig.animation_data is None:
        return {}
    fcus = {}
    for fcu in rig.animation_data.drivers:
        words = fcu.data_path.split('"')
        if (words[0] == "pose.bones[" and
            words[1] in bones and
            len(words) == 3):
            bname = words[1]
            if bname not in fcus.keys():
                fcus[bname] = []
            fcus[bname].append(fcu)
    return fcus


def storeBoneDrivers(rig, bones):
    fcus = getAllBoneDrivers(rig, bones)
    drivers = {}
    for bname in fcus.keys():
        drivers[bname] = []
        for fcu in fcus[bname]:
            drivers[bname].append(Driver(fcu))
    removeDriverFCurves(flatten(fcus.values()), rig)
    return drivers


def flatten(lists):
    flat = []
    for list in lists:
        flat.extend(list)
    return flat


def restoreBoneDrivers(rig, drivers, suffix):
    for bname,bdrivers in drivers.items():
        for driver in bdrivers:
            driver.create(rig, bname+suffix)


def removeBoneDrivers(rig, bones):
    fcus = getAllBoneDrivers(rig, bones)
    removeDriverFCurves(flatten(fcus.values()), rig)


def removeDriverFCurves(fcus, rig):
    for fcu in fcus:
        try:
            rig.driver_remove(fcu.data_path, fcu.array_index)
        except TypeError:
            pass


def removeRigDrivers(rig):
    if rig.animation_data is None:
        return
    fcus = []
    for fcu in rig.animation_data.drivers:
        if ("evalMorphs" in fcu.driver.expression or
            isNumber(fcu.driver.expression)):
            fcus.append(fcu)
    removeDriverFCurves(fcus, rig)


def removePropDrivers(rna, paths=None, rig=None, force=False):
    if rna is None or rna.animation_data is None:
        return False
    fcus = []
    keep = False
    for fcu in rna.animation_data.drivers:
        if paths is None:
            fcus.append(fcu)
        elif force or len(fcu.driver.variables) == 1:
            if matchesPaths(fcu.driver.variables[0], paths, rig):
                fcus.append(fcu)
        else:
            for var in fcu.driver.variables:
                if matchesPaths(var, paths, rig):
                    keep = True
    for fcu in fcus:
        if fcu.data_path:
            try:
                rna.driver_remove(fcu.data_path)
            except TypeError:
                pass
    return keep


def isPropDriver(fcu):
    vars = fcu.driver.variables
    return (len(vars) > 0 and vars[0].type == 'SINGLE_PROP')


def matchesPaths(var, paths, rig):
    if var.type == 'SINGLE_PROP':
        trg = var.targets[0]
        return (trg.id == rig and trg.data_path in paths)
    return False


#----------------------------------------------------------
#   Update button
#----------------------------------------------------------

def updateAll(context):
    updateScene(context)
    for ob in getSceneObjects(context):
        if ob.type == 'ARMATURE':
            updateRig(ob, context)
            #drivers = storeBoneDrivers(ob, list(ob.pose.bones.keys()))
            #restoreBoneDrivers(ob, drivers, "")
        updateDrivers(ob)


class DAZ_OT_UpdateAll(DazOperator):
    bl_idname = "daz.update_all"
    bl_label = "Update All"
    bl_description = "Update everything. Try this if driven bones are messed up"
    bl_options = {'UNDO'}

    def run(self, context):
        updateAll(context)

#-------------------------------------------------------------
#   Restore shapekey drivers
#-------------------------------------------------------------

class DAZ_OT_RestoreDrivers(DazOperator, IsMesh):
    bl_idname = "daz.restore_shapekey_drivers"
    bl_label = "Restore Drivers"
    bl_description = "Restore corrupt shapekey drivers, or change driver target"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        if (ob.data.shape_keys is None or
            ob.data.shape_keys.animation_data is None):
            return
        rig = ob.parent
        if rig is None:
            return

        for fcu in ob.data.shape_keys.animation_data.drivers:
            words = fcu.data_path.split('"')
            if (words[0] == "key_blocks[" and
                len(words) == 3 and
                words[2] == "].value"):
                sname = words[1]
                for var in fcu.driver.variables:
                    trg = var.targets[0]
                    trg.id_type = 'OBJECT'
                    trg.id = rig
                    trg.data_path = '["%s"]' % sname

#----------------------------------------------------------
#   Remove unused drivers
#----------------------------------------------------------

class DAZ_OT_RemoveUnusedDrivers(DazOperator, IsObject):
    bl_idname = "daz.remove_unused_drivers"
    bl_label = "Remove Unused Drivers"
    bl_description = "Remove unused drivers"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSceneObjects(context):
            if getSelected(ob):
                self.removeUnused(ob)
                if ob.data:
                    self.removeUnused(ob.data)
                if ob.type == 'MESH' and ob.data.shape_keys:
                    self.removeUnused(ob.data.shape_keys)
                    self.removeShapekeys(ob.data.shape_keys)
                updateDrivers(ob)
        updateScene(context)


    def removeUnused(self, rna):
        fcus = []
        if rna and rna.animation_data:
            for fcu in rna.animation_data.drivers:
                for var in fcu.driver.variables:
                    for trg in var.targets:
                        if trg.id is None:
                            fcus.append(fcu)
            for fcu in fcus:
                if fcu.data_path:
                    rna.driver_remove(fcu.data_path)


    def removeShapekeys(self, skeys):
        paths = []
        if skeys and skeys.animation_data:
            for fcu in skeys.animation_data.drivers:
                words = fcu.data_path.split('"')
                if words[0] == "key_blocks[":
                    if words[1] not in skeys.key_blocks.keys():
                        paths.append(fcu.data_path)
        for path in paths:
            skeys.driver_remove(path)
        updateDrivers(skeys)

#----------------------------------------------------------
#   Retarget mesh drivers
#----------------------------------------------------------

class DAZ_OT_RetargetDrivers(DazOperator, IsArmature):
    bl_idname = "daz.retarget_mesh_drivers"
    bl_label = "Retarget Mesh Drivers"
    bl_description = "Retarget drivers of selected objects to active object"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        for ob in getSceneObjects(context):
            if getSelected(ob):
                self.retargetRna(ob, rig)
                if ob.data:
                    self.retargetRna(ob.data, rig)
                if ob.type == 'MESH' and ob.data.shape_keys:
                    self.retargetRna(ob.data.shape_keys, rig)


    def retargetRna(self, rna, rig):
        if rna and rna.animation_data:
            for fcu in rna.animation_data.drivers:
                for var in fcu.driver.variables:
                    if var.type == 'SINGLE_PROP':
                        trg = var.targets[0]
                        prop = trg.data_path.split('"')[1]
                        rig[prop] = 0
                    for trg in var.targets:
                        trg.id = rig

#----------------------------------------------------------
#   Copy props
#----------------------------------------------------------

class DAZ_OT_CopyProps(DazOperator, IsObject):
    bl_idname = "daz.copy_props"
    bl_label = "Copy Props"
    bl_description = "Copy properties from selected objects to active object"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob != rig:
                for key in ob.keys():
                    if key not in rig.keys():
                        rig[key] = ob[key]

#----------------------------------------------------------
#   Copy drivers
#----------------------------------------------------------

def copyBoneDrivers(rig1, rig2):
    from .daz import hasSelfRef, copyPropGroups

    if rig1.animation_data:
        struct = {}
        for fcu in rig1.animation_data.drivers:
            words = fcu.data_path.split('"')
            if (len(words) == 3 and
                words[0] == "pose.bones["):
                bname = words[1]
                if bname not in rig2.data.bones.keys():
                    print("Missing bone (copyBoneDrivers):", bname)
                    continue
                copyDriver(fcu, rig2, id=rig2)

        for pb1 in rig1.pose.bones:
            if (pb1.name in rig2.pose.bones.keys() and
                hasSelfRef(pb1)):
                pb2 = rig2.pose.bones[pb1.name]
                copyPropGroups(rig1, rig2, pb2)


class DAZ_OT_CopyBoneDrivers(DazOperator, IsArmature):
    bl_idname = "daz.copy_bone_drivers"
    bl_label = "Copy Bone Drivers"
    bl_description = "Copy bone drivers from selected rig to active rig"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob != rig and ob.type == 'ARMATURE':
                copyBoneDrivers(ob, rig)
                return
        raise DazError("Need two selected armatures")

#----------------------------------------------------------
#   Disable and enable drivers
#----------------------------------------------------------

class DAZ_OT_DisableDrivers(DazOperator):
    bl_idname = "daz.disable_drivers"
    bl_label = "Disable Drivers"
    bl_description = "Disable all face bone drivers to improve performance"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and not ob.DazDriversDisabled)

    def run(self, context):
        rig = context.object
        if rig and rig.animation_data:
            rig.DazDisabledDrivers.clear()
            fcus = []
            for fcu in rig.animation_data.drivers:
                words = fcu.data_path.split('"')
                drv = fcu.driver
                if (words[0] == "pose.bones[" and
                    "evalMorphs" in drv.expression and
                    len(drv.variables) == 0):
                    item = rig.DazDisabledDrivers.add()
                    item.name = words[1]
                    item.index = fcu.array_index
                    item.expression = drv.expression
                    item.channel = words[2].rsplit(".")[-1]
                    fcus.append(fcu)
            removeDriverFCurves(fcus, rig)
            rig.DazDriversDisabled = True


class DAZ_OT_EnableDrivers(DazOperator):
    bl_idname = "daz.enable_drivers"
    bl_label = "Enable Drivers"
    bl_description = "Enable all face bone drivers"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazDriversDisabled)

    def run(self, context):
        rig = context.object
        if rig:
            for item in rig.DazDisabledDrivers:
                pb = rig.pose.bones[item.name]
                fcu = pb.driver_add(item.channel, item.index)
                fcu.driver.use_self = True
                fcu.driver.expression = item.expression
            rig.DazDisabledDrivers.clear()
            rig.DazDriversDisabled = False

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    B.DazDriverGroup,

    DAZ_OT_RestoreDrivers,
    DAZ_OT_RemoveUnusedDrivers,
    DAZ_OT_RetargetDrivers,
    DAZ_OT_CopyProps,
    DAZ_OT_CopyBoneDrivers,
    DAZ_OT_UpdateAll,
    DAZ_OT_DisableDrivers,
    DAZ_OT_EnableDrivers,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.DazDriversDisabled = BoolProperty(default=False)
    bpy.types.Object.DazDisabledDrivers = CollectionProperty(type = B.DazDriverGroup)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
