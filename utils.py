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
import math
from mathutils import Vector
from .settings import GS, LS

#-------------------------------------------------------------
#   Blender 2.8 compatibility
#-------------------------------------------------------------

if bpy.app.version < (2,80,0):

    from . import buttons27 as B

    Region = "TOOLS"
    HideViewport = "hide"
    DrawType = "draw_type"
    ShowXRay = "show_x_ray"

    def getCollection(context):
        return context.scene

    def getSceneObjects(context):
        return context.scene.objects

    def getSelected(ob):
        return ob.select

    def setSelected(ob, value):
        ob.select = value

    def getActiveObject(context):
        return context.scene.objects.active

    def setActiveObject(context, ob):
        try:
            context.scene.objects.active = ob
            return True
        except RuntimeError:
            return False

    def putOnHiddenLayer(ob, coll=None, hidden=None):
        ob.layers = 19*[False] + [True]

    def createHiddenCollection(context):
        return context.scene

    def getUvTextures(me):
        return me.uv_textures

    def inSceneLayer(context, ob):
        if ob.hide:
            return False
        scn = context.scene
        for n in range(len(scn.layers)):
            if (ob.layers[n] and scn.layers[n]):
                return True
        return False

    def showSceneLayer(context, ob):
        scn = context.scene
        for n in range(len(scn.layers)):
            if ob.layers[n]:
                scn.layers[n] = True
                return

    def activateObject(context, ob):
        try:
            if context.object:
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            ob.select = True
        except RuntimeError:
            print("Could not activate", ob)
        context.scene.objects.active = ob

    def Mult2(x, y):
        return x * y

    def Mult3(x, y, z):
        return x * y * z

    def Mult4(x, y, z, u):
        return x * y * z * u

    def splitLayout(layout, factor):
        return layout.split(factor)

    def deleteObject(context, ob):
        if ob is None:
            return
        if context.object:
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        ob.select = True
        for scn in bpy.data.scenes:
            if ob in scn.objects.values():
                scn.objects.unlink(ob)
        for grp in bpy.data.groups:
            if ob.name in grp.objects:
                grp.objects.unlink(ob)
        bpy.ops.object.delete(use_global=False)
        del ob

else:

    from . import buttons28 as B

    Region = "UI"
    HideViewport = "hide_viewport"
    DrawType = "display_type"
    ShowXRay = "show_in_front"

    def getCollection(context):
        return context.collection

    def getSceneObjects(context):
        return context.view_layer.objects

    def getSelected(ob):
        return ob.select_get()

    def setSelected(ob, value):
        ob.select_set(value)

    def getActiveObject(context):
        return context.view_layer.objects.active

    def setActiveObject(context, ob):
        try:
            context.view_layer.objects.active = ob
            return True
        except RuntimeError:
            return False

    def putOnHiddenLayer(ob, coll=None, hidden=None):
        if coll:
            coll.objects.unlink(ob)
        if hidden:
            hidden.objects.link(ob)

    def createHiddenCollection(context):
        coll = bpy.data.collections.new(name="Hidden")
        context.collection.children.link(coll)
        coll.hide_viewport = True
        coll.hide_render = True
        return coll

    def getUvTextures(me):
        return me.uv_layers

    def inSceneLayer(context, ob):
        if ob.hide_viewport:
            return False
        return inCollection(context.view_layer.layer_collection, ob)

    def inCollection(layer, ob):
        if layer.hide_viewport:
            return False
        elif not layer.exclude and ob in layer.collection.objects.values():
            return True
        for child in layer.children:
            if inCollection(child, ob):
                return True
        return False

    def showSceneLayer(context, ob):
        coll = context.collection
        coll.objects.link(ob)

    def activateObject(context, ob):
        try:
            if context.object:
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            ob.select_set(True)
        except RuntimeError:
            print("Could not activate", context.object)
        context.view_layer.objects.active = ob

    def printActive(name, context):
        coll = context.collection
        print(name, context.object, coll)
        sel = [ob for ob in coll.objects if ob.select_get()]
        print("  ", sel)

    def Mult2(x, y):
        return x @ y

    def Mult3(x, y, z):
        return x @ y @ z

    def Mult4(x, y, z, u):
        return x @ y @ z @ u

    def splitLayout(layout, factor):
        return layout.split(factor=factor)

    def deleteObject(context, ob):
        if context.object:
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        for coll in bpy.data.collections:
            if ob in coll.objects.values():
                coll.objects.unlink(ob)
        bpy.ops.object.delete(use_global=False)
        del ob

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def updateScene(context):
    if bpy.app.version < (2,80,0):
        scn = context.scene
        scn.update()
        scn.frame_current = scn.frame_current
    else:
        depth = context.evaluated_depsgraph_get()
        depth.update()


def toggleEditMode():
    try:
        bpy.ops.object.editmode_toggle()
        bpy.ops.object.editmode_toggle()
    except RuntimeError:
        print("Could not update", bpy.context.object)
        pass

def updateRig(rig, context):
    ob = context.object
    if ob is None:
        return
    if bpy.app.version >= (2,80,0):
        if ob.type == 'MESH':
            context.view_layer.objects.active = rig
            bpy.ops.object.posemode_toggle()
            bpy.ops.object.posemode_toggle()
            context.view_layer.objects.active = ob
        elif ob.type == 'ARMATURE':
            bpy.ops.object.posemode_toggle()
            bpy.ops.object.posemode_toggle()

    else:
        if ob.type == "MESH":
            context.scene.objects.active = rig
            if rig.mode == "POSE":
                pos = rig.pose.bones[0].location[0]
                rig.pose.bones[0].location[0] = pos + 0
            elif rig.mode == "OBJECT":
                bpy.ops.object.posemode_toggle()
                pos = rig.pose.bones[0].location[0]
                rig.pose.bones[0].location[0] = pos + 0
                bpy.ops.object.posemode_toggle()
            context.scene.objects.active = ob

        elif ob.type == 'ARMATURE':
            if rig.mode == "POSE":
                pos = rig.pose.bones[0].location[0]
                rig.pose.bones[0].location[0] = pos + 0
            elif rig.mode == "OBJECT":
                bpy.ops.object.posemode_toggle()
                pos = rig.pose.bones[0].location[0]
                rig.pose.bones[0].location[0] = pos + 0
                bpy.ops.object.posemode_toggle()


def updateDrivers(ob):
    if ob and ob.animation_data:
        for fcu in ob.animation_data.drivers:
            string = str(fcu.driver.expression)
            fcu.driver.expression = string


def getName(string):
    from .asset import normalizePath
    return normalizePath(string.split("#")[-1])


def instRef(ref):
    return ref.rsplit("#",1)[-1]


def tolower(url):
    if not GS.caseSensitivePaths:
        return url.lower()
    else:
        return url


def clamp(value):
    return min(1, max(0, value))


def isVector(value):
    return hasattr(value, "__len__")


def averageColor(value):
    if isVector(value):
        x,y,z = value
        return (x+y+z)/3
    else:
        return value


def match(tests, string):
    for test in tests:
        if test in string:
            return test
    return None


def sorted(seq):
    slist = list(seq)
    slist.sort()
    return slist


def hasPoseBones(rig, bnames):
    for bname in bnames:
        if bname not in rig.pose.bones.keys():
            return False
    return True


def getCurrentValue(struct, default=None):
    if "current_value" in struct.keys():
        return struct["current_value"]
    elif "value" in struct.keys():
        return struct["value"]
    else:
        return default

#-------------------------------------------------------------
#   Profiling
#-------------------------------------------------------------

from time import perf_counter

class Timer:
    def __init__(self):
        self.t = perf_counter()

    def print(self, msg):
        t = perf_counter()
        print("%8.6f: %s" % (t-self.t, msg))
        self.t = t

#-------------------------------------------------------------
#   Progress
#-------------------------------------------------------------

def startProgress(string):
    print(string)
    wm = bpy.context.window_manager
    wm.progress_begin(0, 100)

def endProgress():
    wm = bpy.context.window_manager
    wm.progress_update(100)
    wm.progress_end()

def showProgress(n, total):
    pct = (100.0*n)/total
    wm = bpy.context.window_manager
    wm.progress_update(int(pct))

#-------------------------------------------------------------
#   Coords
#-------------------------------------------------------------

def getIndex(id):
    if id == "x": return 0
    elif id == "y": return 1
    elif id == "z": return 2
    else: return -1


def getCoord(p):
    co = Vector((0,0,0))
    for c in p:
        co[getIndex(c["id"])] = c["value"]
    return d2b(co)


def d2b90(v):
    return LS.scale*Vector((v[0], -v[2], v[1]))

def b2d90(v):
    return Vector((v[0], v[2], -v[1]))/LS.scale

def d2b90u(v):
    return Vector((v[0], -v[2], v[1]))

def d2b90s(v):
    return Vector((v[0], v[2], v[1]))


def d2b00(v):
    return LS.scale*Vector(v)

def b2d00(v):
    return Vector(v)/LS.scale

def d2b00u(v):
    return Vector(v)

def d2b00s(v):
    return Vector(v)


def d2b(v):
    if GS.zup:
        return d2b90(v)
    else:
        return d2b00(v)

def b2d(v):
    if GS.zup:
        return b2d90(v)
    else:
        return b2d00(v)

def d2bu(v):
    if GS.zup:
        return d2b90u(v)
    else:
        return d2b00u(v)

def d2bs(v):
    if GS.zup:
        return d2b90s(v)
    else:
        return d2b00s(v)


def vector(comp, value):
    if comp == "x":
        return LS.scale*Vector((value,0,0))
    elif comp == "y":
        return LS.scale*Vector((0,value,0))
    elif comp == "z":
        return LS.scale*Vector((0,0,value))

D2R = "%.6f*" % (math.pi/180)
D = math.pi/180



