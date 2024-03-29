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


import os
import json
import bpy
from bpy.props import *
from .utils import *
from .error import *
from .material import MaterialMerger
import string
import random
from collections import OrderedDict



#-------------------------------------------------------------
#   Merge geografts
#-------------------------------------------------------------

class DAZ_OT_MergeGeograftsNonDestructive(DazOperator, MaterialMerger, IsMesh):
    bl_idname = "daz.merge_geografts_nondestructive"
    bl_label = "Merge Geografts Safe"
    bl_description = "Merge selected geografts to active object Non Destructive (keep original mesh faces)"
    bl_options = {'UNDO'}


    def run(self, context):
        from .driver import getShapekeyDrivers, copyShapeKeyDrivers


        #cob = bpy.data.objects['Genesis 3 Female Mesh']
        #aob = bpy.data.objects['Genesis 3 Female Genitalia.001']

        cob = context.object
        ncverts = len(cob.data.vertices)

        # Find anatomies and move graft verts into position
        anatomies = []
        for aob in getSceneObjects(context):
            if (aob.type == 'MESH' and
                getSelected(aob) and
                aob != cob and
                aob.data.DazGraftGroup):
                anatomies.append(aob)

        if len(anatomies) < 1:
            raise DazError("At least two meshes must be selected.\nGeografts selected and target active.")

        for aob in anatomies:
            if aob.data.DazVertexCount != ncverts:
                if cob.data.DazVertexCount == len(aob.data.vertices):
                    msg = ("Meshes selected in wrong order.\nGeografts selected and target active.   ")
                else:
                    msg = ("Geograft %s fits mesh with %d vertices,      \nbut %s has %d vertices." %
                        (aob.name, aob.data.DazVertexCount, cob.name, ncverts))
                raise DazError(msg)

        cname = self.getUvName(cob.data)
        anames = []
        drivers = {}

        # Keep extra UVs
        self.keepUv = []
        for ob in [cob] + anatomies:
            for uvtex in getUvTextures(ob.data):
                if not uvtex.active_render:
                    self.keepUv.append(uvtex.name)

        # Select graft group for each anatomy
        for aob in anatomies:
            activateObject(context, aob)
            self.moveGraftVerts(aob, cob) # moveGraftVerts: moves all common geograft vertices to the location of the coresponding vertices. It also `fixes` the vertices in shared shapekey names
            getShapekeyDrivers(aob, drivers)
            for uvtex in getUvTextures(aob.data):
                if uvtex.active_render:
                    anames.append(uvtex.name)
                else:
                    self.keepUv.append(uvtex.name)





        preservableVertexIndices = []
        removableEdgeIndices = []
        for aob in anatomies:                    

            # those are the faces on geograft that daz is supposed to mask/hide/remove when the geograft is applied   
            # all faces !!! included in the geograft boundaries/replaceable faces also the ones to be removed         
            # but this is a complicated problem, if we delete the edges a bit later, it also shifts the faces count, so maybe we can't delete them?!? maybe later?!?
            maskedFaceIndices = [ item.a for item in aob.data.DazMaskGroup ]

            # but from those faces, we are going to get the vertices that makes them
            # all vertices !!! included in the geograft boundaries/replaceable vertices also the ones to be removed
            maskedVertexIndices = []
            for findex in maskedFaceIndices:
                vIndexArray = [cob.data.polygons[findex].vertices[i] for i in range(len(cob.data.polygons[findex].vertices))]  #there can be faces made from 3 or 4 vertices 
                maskedVertexIndices.extend(vIndexArray)

            # list of vertices that are merged in the body
            mergingBodyVerticesList=[]
            for item in aob.data.DazGraftGroup:
                mergingBodyVerticesList.append(item.b)

            # those are the vertices we should in theory to keep (those are not on the merging boundary)
            preservableVertexIndices = []
            for element in maskedVertexIndices:
                if element not in mergingBodyVerticesList:
                    preservableVertexIndices.append(element)



            #preservableVertexIndices = maskedVertexIndices - mergingBodyVerticesList

            for edge in cob.data.edges:
                v1 = edge.vertices[0]
                v2 = edge.vertices[1]
                if v1 in maskedVertexIndices and v2 in maskedVertexIndices: #if both vertices of the edge are in the geograft merging/replaceable vertices list
                    if v1 in mergingBodyVerticesList and v2 in mergingBodyVerticesList: #if both vertices of the edge are to be merged/replaced then ignore this edge
                        continue
                    if v1 in preservableVertexIndices and v2 in preservableVertexIndices: #this is the edge we want to keep in order to maintain the face (easy scaling)
                        continue
                    removableEdgeIndices.append(edge.index) # finally we find an edge that is not in the boundary and we dont want to keep



        activateObject(context, cob)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(type="EDGE")
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        #
        # in this version of merge geografts we don't remove edges/vertices/whatsoever, we try to keep original geometry intact
        #
        #    for edgeIndex in removableEdgeIndices:
        #        cob.data.edges[edgeIndex].select= True
        #    bpy.ops.object.mode_set(mode='EDIT')
        #    ##############################################################################################################
        #    bpy.ops.mesh.delete(type='EDGE')                        # DELETE EDGE
        ##############################################################################################################
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.object.mode_set(mode='OBJECT')

        rvs = OrderedDict()
        for aob in anatomies:
            aobVertexCount = len(aob.data.vertices)
            dazGraftGroupAfterJoinDict=OrderedDict()
            for item in aob.data.DazGraftGroup:
                print("original matching: {0}:{1}".format(item.a,item.b))
                dazGraftGroupAfterJoinDict[item.a+len(cob.data.vertices)]=item.b                  #that -1 is very important, tricky!!!
            for k, v in dazGraftGroupAfterJoinDict.items():
                print("shifted matching: {0}:{1}".format(k,v))
            rvs = reversed(dazGraftGroupAfterJoinDict.items())
            for k, v in rvs:
                print("reversed - {0}:{1}".format(k,v))

            setSelected(aob, True)
            activateObject(context, cob)
            setSelected(aob, True)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')

            bpy.ops.object.join()
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            counter= 0
            print("rvs size...")
            rvs = reversed(dazGraftGroupAfterJoinDict.items())
            for k, v in rvs:
                print("merging - {0}:{1}".format(k,v))
                cob.data.vertices[v].select = True # this is the vertex added from the aob (anatomy)
                cob.data.vertices[k].select = True # this is the original vertex from cob (body)
                #
                counter = counter+1
                bpy.ops.object.mode_set(mode='EDIT')
                #cob.data.vertices[v].co = cob.data.vertices[k].co 
                bpy.ops.mesh.merge(type='CENTER', uvs=False)
                #threshold = 0.001*cob.DazScale
                #bpy.ops.mesh.remove_doubles(threshold=threshold)   
                bpy.ops.mesh.select_all(action='DESELECT')             
                bpy.ops.object.mode_set(mode='OBJECT')
                #ob.data.update()
            #
            # we no longer need to hide (scale = 0 ) the unconected vertices, because those are still connected
            #    for p in preservableVertexIndices:
            #        cob.data.vertices[p].select = True 
            #    bpy.ops.object.mode_set(mode='EDIT')
            #    bpy.ops.transform.resize(value=(0.0, 0.0, 0.0) )
            #    bpy.ops.mesh.select_all(action='DESELECT')

        bpy.ops.object.mode_set(mode='OBJECT')
        self.joinUvTextures(cob.data)

        newname = self.getUvName(cob.data)
        for mat in cob.data.materials:
            if mat.use_nodes:
                replaceNodeNames(mat, cname, newname)
                for aname in anames:
                    replaceNodeNames(mat, aname, newname)

        # Remove unused materials
        self.mathits = dict([(mn,False) for mn in range(len(cob.data.materials))])
        for f in cob.data.polygons:
            self.mathits[f.material_index] = True
        self.mergeMaterials(cob)

        copyShapeKeyDrivers(cob, drivers)
        updateDrivers(cob)            
    
    
    def keepMaterial(self, mn, mat, ob):
        keep = self.mathits[mn]
        if not keep:
            print("Remove material %s" % mat.name)
        return keep


    def moveGraftVerts(self, aob, cob):
        """ This function moves all common geograft vertices to the location of the coresponding vertices.\n It also `fixes` the vertices in shared shapekey names"""
        for pair in aob.data.DazGraftGroup:
            print("{0:d},{1:d}".format(pair.a,pair.b))
            aob.data.vertices[pair.a].co = cob.data.vertices[pair.b].co
        if cob.data.shape_keys and aob.data.shape_keys:
            for cskey in cob.data.shape_keys.key_blocks:
                if cskey.name in aob.data.shape_keys.key_blocks.keys():
                    askey = aob.data.shape_keys.key_blocks[cskey.name]
                    for pair in aob.data.DazGraftGroup:
                        askey.data[pair.a].co = cskey.data[pair.b].co


    def joinUvTextures(self, me):
        if len(me.uv_layers) <= 1:
            return
        for n,data in enumerate(me.uv_layers[0].data):
            if data.uv.length < 1e-6:
                for uvloop in me.uv_layers[1:]:
                    if uvloop.data[n].uv.length > 1e-6:
                        data.uv = uvloop.data[n].uv
                        break
        for uvtex in list(getUvTextures(me)[1:]):
            if uvtex.name not in self.keepUv:
                try:
                    getUvTextures(me).remove(uvtex)
                except RuntimeError:
                    print("Cannot remove texture layer '%s'" % uvtex.name)


    def getUvName(self, me):
        for uvtex in getUvTextures(me):
            if uvtex.active_render:
                return uvtex.name
        return None



#-------------------------------------------------------------
#   Merge geografts
#-------------------------------------------------------------

class DAZ_OT_MergeGeograftsFast(DazOperator, MaterialMerger, IsMesh):
    bl_idname = "daz.merge_geografts_fast"
    bl_label = "Merge Geografts Fast"
    bl_description = "Merge selected geografts to active object (fast version)"
    bl_options = {'UNDO'}


    def run(self, context):
        from .driver import getShapekeyDrivers, copyShapeKeyDrivers


        #cob = bpy.data.objects['Genesis 3 Female Mesh']
        #aob = bpy.data.objects['Genesis 3 Female Genitalia.001']

        cob = context.object
        ncverts = len(cob.data.vertices)

        # Find anatomies and move graft verts into position
        anatomies = []
        for aob in getSceneObjects(context):
            if (aob.type == 'MESH' and
                getSelected(aob) and
                aob != cob and
                aob.data.DazGraftGroup):
                anatomies.append(aob)

        if len(anatomies) < 1:
            raise DazError("At least two meshes must be selected.\nGeografts selected and target active.")

        for aob in anatomies:
            if aob.data.DazVertexCount != ncverts:
                if cob.data.DazVertexCount == len(aob.data.vertices):
                    msg = ("Meshes selected in wrong order.\nGeografts selected and target active.   ")
                else:
                    msg = ("Geograft %s fits mesh with %d vertices,      \nbut %s has %d vertices." %
                        (aob.name, aob.data.DazVertexCount, cob.name, ncverts))
                raise DazError(msg)

        cname = self.getUvName(cob.data)
        anames = []
        drivers = {}

        # Keep extra UVs
        self.keepUv = []
        for ob in [cob] + anatomies:
            for uvtex in getUvTextures(ob.data):
                if not uvtex.active_render:
                    self.keepUv.append(uvtex.name)

        # Select graft group for each anatomy
        for aob in anatomies:
            activateObject(context, aob)
            self.moveGraftVerts(aob, cob) # moveGraftVerts: moves all common geograft vertices to the location of the coresponding vertices. It also `fixes` the vertices in shared shapekey names
            getShapekeyDrivers(aob, drivers)
            for uvtex in getUvTextures(aob.data):
                if uvtex.active_render:
                    anames.append(uvtex.name)
                else:
                    self.keepUv.append(uvtex.name)





        preservableVertexIndices = []
        removableEdgeIndices = []
        for aob in anatomies:                    

            # those are the faces on geograft that daz is supposed to mask/hide/remove when the geograft is applied   
            # all faces !!! included in the geograft boundaries/replaceable faces also the ones to be removed         
            # but this is a complicated problem, if we delete the edges a bit later, it also shifts the faces count, so maybe we can't delete them?!? maybe later?!?
            maskedFaceIndices = [ item.a for item in aob.data.DazMaskGroup ]

            # but from those faces, we are going to get the vertices that makes them
            # all vertices !!! included in the geograft boundaries/replaceable vertices also the ones to be removed
            maskedVertexIndices = []
            for findex in maskedFaceIndices:
                vIndexArray = [cob.data.polygons[findex].vertices[i] for i in range(len(cob.data.polygons[findex].vertices))]  #there can be faces made from 3 or 4 vertices 
                maskedVertexIndices.extend(vIndexArray)

            # list of vertices that are merged in the body
            mergingBodyVerticesList=[]
            for item in aob.data.DazGraftGroup:
                mergingBodyVerticesList.append(item.b)

            # those are the vertices we should in theory to keep (those are not on the merging boundary)
            preservableVertexIndices = []
            for element in maskedVertexIndices:
                if element not in mergingBodyVerticesList:
                    preservableVertexIndices.append(element)



            #preservableVertexIndices = maskedVertexIndices - mergingBodyVerticesList

            for edge in cob.data.edges:
                v1 = edge.vertices[0]
                v2 = edge.vertices[1]
                if v1 in maskedVertexIndices and v2 in maskedVertexIndices: #if both vertices of the edge are in the geograft merging/replaceable vertices list
                    if v1 in mergingBodyVerticesList and v2 in mergingBodyVerticesList: #if both vertices of the edge are to be merged/replaced then ignore this edge
                        continue
                    if v1 in preservableVertexIndices and v2 in preservableVertexIndices: #this is the edge we want to keep in order to maintain the face (easy scaling)
                        continue
                    removableEdgeIndices.append(edge.index) # finally we find an edge that is not in the boundary and we dont want to keep



        activateObject(context, cob)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(type="EDGE")
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        for edgeIndex in removableEdgeIndices:
            cob.data.edges[edgeIndex].select= True
        bpy.ops.object.mode_set(mode='EDIT')
        ##############################################################################################################
        bpy.ops.mesh.delete(type='EDGE')                        # DELETE EDGE
        ##############################################################################################################
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.object.mode_set(mode='OBJECT')

        rvs = OrderedDict()
        for aob in anatomies:
            aobVertexCount = len(aob.data.vertices)
            dazGraftGroupAfterJoinDict=OrderedDict()
            for item in aob.data.DazGraftGroup:
                print("original matching: {0}:{1}".format(item.a,item.b))
                dazGraftGroupAfterJoinDict[item.a+len(cob.data.vertices)]=item.b                  #that -1 is very important, tricky!!!
            for k, v in dazGraftGroupAfterJoinDict.items():
                print("shifted matching: {0}:{1}".format(k,v))
            rvs = reversed(dazGraftGroupAfterJoinDict.items())
            for k, v in rvs:
                print("reversed - {0}:{1}".format(k,v))

            setSelected(aob, True)
            activateObject(context, cob)
            setSelected(aob, True)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')

            bpy.ops.object.join()
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            counter= 0
            print("rvs size...")
            rvs = reversed(dazGraftGroupAfterJoinDict.items())
            for k, v in rvs:
                print("merging - {0}:{1}".format(k,v))
                cob.data.vertices[v].select = True # this is the vertex added from the aob (anatomy)
                cob.data.vertices[k].select = True # this is the original vertex from cob (body)
                #
                counter = counter+1
                bpy.ops.object.mode_set(mode='EDIT')
                #cob.data.vertices[v].co = cob.data.vertices[k].co 
                bpy.ops.mesh.merge(type='CENTER', uvs=False)
                #threshold = 0.001*cob.DazScale
                #bpy.ops.mesh.remove_doubles(threshold=threshold)   
                bpy.ops.mesh.select_all(action='DESELECT')             
                bpy.ops.object.mode_set(mode='OBJECT')
                #ob.data.update()
            #
            #range ( start , end , increment/decrement ) where start is inclusive , end is exclusive and increment can be any numbers and behaves like step  
            #for k, v in rvs:
            #    print("merging - {0}:{1}".format(k,v))
            #    cob.data.vertices[k].select = True # this is the vertex added from the aob (anatomy)            
            #for c in range (len(cob.data.vertices)-1, len(cob.data.vertices) - aobVertexCount -1,-1):
            #    cob.data.vertices[c].select = True
            #for k, v in reversed(dazGraftGroupAfterJoinDict.items()):
            #    print("{0}:{1}".format(k,v))
            #    cob.data.vertices[k].select = True # this is the vertex added from the aob (anatomy)
            for p in preservableVertexIndices:
                cob.data.vertices[p].select = True 
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.transform.resize(value=(0.0, 0.0, 0.0) )
            bpy.ops.mesh.select_all(action='DESELECT')

        bpy.ops.object.mode_set(mode='OBJECT')
        self.joinUvTextures(cob.data)

        newname = self.getUvName(cob.data)
        for mat in cob.data.materials:
            if mat.use_nodes:
                replaceNodeNames(mat, cname, newname)
                for aname in anames:
                    replaceNodeNames(mat, aname, newname)

        # Remove unused materials
        self.mathits = dict([(mn,False) for mn in range(len(cob.data.materials))])
        for f in cob.data.polygons:
            self.mathits[f.material_index] = True
        self.mergeMaterials(cob)

        copyShapeKeyDrivers(cob, drivers)
        updateDrivers(cob)            
        """   
            activateObject(context, cob)
            setSelected(cob, True)

         
            bpy.ops.object.join()
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')

        """
        """
        for aob in anatomies:
            activateObject(context, aob)
            setSelected(aob, True)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')

            



        # For the body, setup mask groups
        activateObject(context, cob)
        nverts = len(cob.data.vertices)
        vfaces = dict([(vn,[]) for vn in range(nverts)]) # {0: [9337, 9346, 10746, 10755], 1: [9806, 9811, 11215, 11220], 2: [1685, 2398, 8644, 10053], 3: [2047, 2760, 9922, 11331], 4: [9156, 9157, 10565, 10566], 5: [9155, 9203, 10564, 10612], 6: [9154, 9155, 10563, 10564], 7: [9154, 9409, 10563, 10818], 8: [1978, 1986, 2691, 2699], 9: [1975, 1983, 2688, 2696], 10: [1978, 1980, 2691, 2693], 11: [1685, 2165, 2398, 2878], 12: [9158, 9169, 10567, 10578], 13: [3086, 3103, 3188, 3205], ...}
        for f in cob.data.polygons:                      # 0 is the vertex index, and 9337, 9346, 10746, 10755 are faces the 0 indexed vertex belongs to !!! (is not the other way around!!!)
            for vn in f.vertices:
                vfaces[vn].append(f.index) #we build vertex index array which holds all faces index that contains this vertex

        masked_array =[]  #added by me
        nfaces = len(cob.data.polygons)
        #fmasked is going to tell me which face is masked (which face index)
        fmasked = dict([(fn,False) for fn in range(nfaces)]) #we init as false first {0: False, 1: False, 2: False, 3: False, 4: False, 5: False, 6: False, 7: False, 8: False, 9: False, 10: False, 11: False, 12: False, 13: False, ...}
        for aob in anatomies:
            for face in aob.data.DazMaskGroup: # DazMaskGroup = hidden_polys
                fmasked[face.a] = True
                masked_array.append(face.a)

        print("masked array is:\n")
        print (str(masked_array)[1:-1]) 
        # If cob is itself a geograft, make sure to keep the boundary
        if cob.data.DazGraftGroup:
            cgrafts = [pair.a for pair in cob.data.DazGraftGroup]
        else:
            cgrafts = [] # but if cob is not a geograft, then cgrafts is emtpy

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        # Select body verts to delete
        vdeleted = dict([(vn,False) for vn in range(nverts)])
        for aob in anatomies:
            paired = [pair.b for pair in aob.data.DazGraftGroup]
            for face in aob.data.DazMaskGroup:  # for every hidden_face
                fverts = cob.data.polygons[face.a].vertices #face.a is the index of the hidden_face
                vdelete = []
                for vn in fverts: #this is an actually _for_loop_ for every vertex that belongs to a face that is a hidden_face
                    if vn in cgrafts:
                        pass
                    elif vn not in paired: #if the vertex belongs to a hidden_face, but is not in vertex_pairs (common in both meshes)
                        vdelete.append(vn) # then we add it to the deletion list
                    else:
                        mfaces = [fn for fn in vfaces[vn] if fmasked[fn]] # this is a dictionary like vfaces, but only if is masked
                        if len(mfaces) == len(vfaces[vn]):                # so for a vertex (vn is the index) we look at adiacent faces and put all those faces in an array
                            vdelete.append(vn)                            # and if the mfaces (all faces adiacent to an index that are hidden_face-s) is the same as the all faces adiacent
                #                                                         # more exactly, in simple translate, if all faces adiacent to a vertex are also hidden
                #                                                         # then we add that vertex index to the deletion list
                for vn in vdelete:                         
                    cob.data.vertices[vn].select = True
                    vdeleted[vn] = True

        # Build association table between new and old vertex numbers
        assoc = {}  #when we delete the vertices, a remaining vertex takes the position of the deleted one, vertices index is shifted
        vn2 = 0     #so vn2 is the new vn vertex
        for vn in range(nverts):
            if not vdeleted[vn]:
                assoc[vn] = vn2
                vn2 += 1

        aobDazGraftGroupCounter = len (aob.data.DazGraftGroup)
        newVertexGroupPrefix = id_generator()+id_generator()+"_"
        for index,pair in enumerate(aob.data.DazGraftGroup):
            newVertexGroup = aob.vertex_groups.new(name=newVertexGroupPrefix+str(index))
            newVertexGroup.add([pair.a], 0.0, 'ADD')
            newVertexGroup = cob.vertex_groups.new(name=newVertexGroupPrefix+str(index))
            newVertexGroup.add([pair.b], 0.0, 'ADD')
        
        aobVerts = [v.index for v in aob.data.vertices]
        newVertexGroup = aob.vertex_groups.new(name=newVertexGroupPrefix+"all_vertices")
        newVertexGroup.add(aobVerts, 0.0, 'ADD')

        # Delete the masked verts
        bpy.ops.object.mode_set(mode='EDIT')
        #bpy.ops.mesh.delete(type='VERT')
        bpy.ops.object.mode_set(mode='OBJECT')

        # If cob is itself a geograft, store locations
        if cob.data.DazGraftGroup:
            verts = cob.data.vertices
            locations = dict([(pair.a, verts[pair.a].co.copy()) for pair in cob.data.DazGraftGroup])


        #hfg2 changes
        # first Select both graft and body and deselect vertices in edit mode
        # Select verts on common boundary
        names = []
        for aob in anatomies:
            setSelected(aob, True)
            names.append(aob.name)
        
        print("Merge %s to %s" % (names, cob.name))


        activateObject(context, cob)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        for aob in anatomies:
            activateObject(context, aob)
            setSelected(aob, True)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')

        activateObject(context, cob)
        setSelected(cob, True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        setSelected(aob, True)
        activateObject(context, cob)
        setSelected(aob, True)
        



        bpy.ops.object.join()
        
        # Deselect all verts
        bpy.ops.object.mode_set( mode = 'EDIT' )
        bpy.ops.mesh.select_all( action = 'DESELECT' )
        #bpy.ops.object.mode_set( mode = 'OBJECT' )
        #bpy.ops.object.mode_set(mode="EDIT")        
        #all vertex groups starts with newVertexGroupPrefix + +str(index)
        threshold = 0.001*cob.DazScale
        vgroups = cob.vertex_groups
        
        for index in range(aobDazGraftGroupCounter): # for index,notUsed in enumerate(aob.data.DazGraftGroup):
            print("Selecting indices for group: "+str(newVertexGroupPrefix+str(index)))
            vgroups.active_index = vgroups[newVertexGroupPrefix+str(index)].index
            bpy.ops.object.vertex_group_select()
            #bpy.ops.mesh.merge(type='CENTER', uvs=False)
            bpy.ops.mesh.remove_doubles(threshold=threshold)
            bpy.ops.object.vertex_group_deselect()
            #bpy.ops.mesh.select_all( action = 'DESELECT' )
            #bpy.ops.object.mode_set(mode='OBJECT')
            # Now the selected vertices are the ones that belong to this VG
            #vgVerts = [ v for v in o.data.vertices if v.select ]

            #   [vert for vert in cob.data.vertices if cob.vertex_groups[newVertexGroupPrefix+str(index)].index in [i.group for i in vert.groups]]
            # vg_idx = 0
            #o = bpy.context.object
            #vs = [ v for v in o.data.vertices if vg_idx in [ vg.group for vg in v.groups ] ]
        
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode="EDIT")

        for index in range(aobDazGraftGroupCounter): #for index,notUsed in enumerate(aob.data.DazGraftGroup):
            vgroups.active_index = vgroups[newVertexGroupPrefix+str(index)].index
            bpy.ops.object.vertex_group_select()
        vgroups.active_index = vgroups[newVertexGroupPrefix+"all_vertices"].index
        bpy.ops.object.vertex_group_select()

        #if 1==True:
        #    return {'FINISHED'}

        selected = dict([(v.index,v.co.copy()) for v in cob.data.vertices if v.select])

        bpy.ops.object.mode_set(mode='OBJECT')

        if True == False :
            #if 1==True:
            #    return {'FINISHED'}
            # ///////////////////////////////////////////////////////////// old code ///////////////////////////////////
            # Select nothing
            for aob in anatomies:
                activateObject(context, aob)
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='DESELECT')
                bpy.ops.object.mode_set(mode='OBJECT')
            activateObject(context, cob)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            # Select verts on common boundary
            names = []
            for aob in anatomies:
                setSelected(aob, True)
                names.append(aob.name)
                for pair in aob.data.DazGraftGroup:
                    aob.data.vertices[pair.a].select = True
                    if pair.b in assoc.keys():
                        cvn = assoc[pair.b]
                        cob.data.vertices[cvn].select = True
            
            
            # Also select cob graft group. These will not be removed.
            if cob.data.DazGraftGroup:
                for pair in cob.data.DazGraftGroup:
                    cvn = assoc[pair.a]
                    cob.data.vertices[cvn].select = True



            # Join meshes and remove doubles
            print("Merge %s to %s" % (names, cob.name))
            threshold = 0.001*cob.DazScale
            bpy.ops.object.join()
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.remove_doubles(threshold=threshold)
            bpy.ops.object.mode_set(mode='OBJECT')
            selected = dict([(v.index,v.co.copy()) for v in cob.data.vertices if v.select])
            bpy.ops.object.mode_set(mode='EDIT')
            if 1==True:
                return {'FINISHED'}
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')

        # Update cob graft group
        if cob.data.DazGraftGroup and selected:
            for pair in cob.data.DazGraftGroup:
                x = locations[pair.a]
                dists = [((x-y).length, vn) for vn,y in selected.items()]
                dists.sort()
                pair.a = dists[0][1]

        self.joinUvTextures(cob.data)

        #hfg2 cleanup merging groups, since we no longer need those we can remove them
        vgs = [vg for vg in cob.vertex_groups if vg.name.find(newVertexGroupPrefix) != -1]
        while(vgs):
            cob.vertex_groups.remove(vgs.pop())

        newname = self.getUvName(cob.data)
        for mat in cob.data.materials:
            if mat.use_nodes:
                replaceNodeNames(mat, cname, newname)
                for aname in anames:
                    replaceNodeNames(mat, aname, newname)

        # Remove unused materials
        self.mathits = dict([(mn,False) for mn in range(len(cob.data.materials))])
        for f in cob.data.polygons:
            self.mathits[f.material_index] = True
        self.mergeMaterials(cob)

        copyShapeKeyDrivers(cob, drivers)
        updateDrivers(cob)
            """
    
    def keepMaterial(self, mn, mat, ob):
        keep = self.mathits[mn]
        if not keep:
            print("Remove material %s" % mat.name)
        return keep


    def moveGraftVerts(self, aob, cob):
        """ This function moves all common geograft vertices to the location of the coresponding vertices.\n It also `fixes` the vertices in shared shapekey names"""
        for pair in aob.data.DazGraftGroup:
            print("{0:d},{1:d}".format(pair.a,pair.b))
            aob.data.vertices[pair.a].co = cob.data.vertices[pair.b].co
        if cob.data.shape_keys and aob.data.shape_keys:
            for cskey in cob.data.shape_keys.key_blocks:
                if cskey.name in aob.data.shape_keys.key_blocks.keys():
                    askey = aob.data.shape_keys.key_blocks[cskey.name]
                    for pair in aob.data.DazGraftGroup:
                        askey.data[pair.a].co = cskey.data[pair.b].co


    def joinUvTextures(self, me):
        if len(me.uv_layers) <= 1:
            return
        for n,data in enumerate(me.uv_layers[0].data):
            if data.uv.length < 1e-6:
                for uvloop in me.uv_layers[1:]:
                    if uvloop.data[n].uv.length > 1e-6:
                        data.uv = uvloop.data[n].uv
                        break
        for uvtex in list(getUvTextures(me)[1:]):
            if uvtex.name not in self.keepUv:
                try:
                    getUvTextures(me).remove(uvtex)
                except RuntimeError:
                    print("Cannot remove texture layer '%s'" % uvtex.name)


    def getUvName(self, me):
        for uvtex in getUvTextures(me):
            if uvtex.active_render:
                return uvtex.name
        return None


class DAZ_OT_MergeGeografts(DazOperator, MaterialMerger, IsMesh):
    bl_idname = "daz.merge_geografts"
    bl_label = "Merge Geografts"
    bl_description = "Merge selected geografts to active object"
    bl_options = {'UNDO'}


    def run(self, context):
        from .driver import getShapekeyDrivers, copyShapeKeyDrivers

        #define a random generator string function, we can use this to create a custom temporary name for vertex groups used in merging
        def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
            return ''.join(random.choice(chars) for _ in range(size))
        
        id_gen = id_generator()
        #cob = bpy.data.objects['Genesis 3 Female Mesh']
        #aob = bpy.data.objects['Genesis 3 Female Genitalia.001']

        print (id_gen)
        cob = context.object
        ncverts = len(cob.data.vertices)

        # Find anatomies and move graft verts into position
        anatomies = []
        for aob in getSceneObjects(context):
            if (aob.type == 'MESH' and
                getSelected(aob) and
                aob != cob and
                aob.data.DazGraftGroup):
                anatomies.append(aob)

        if len(anatomies) < 1:
            raise DazError("At least two meshes must be selected.\nGeografts selected and target active.")

        for aob in anatomies:
            if aob.data.DazVertexCount != ncverts:
                if cob.data.DazVertexCount == len(aob.data.vertices):
                    msg = ("Meshes selected in wrong order.\nGeografts selected and target active.   ")
                else:
                    msg = ("Geograft %s fits mesh with %d vertices,      \nbut %s has %d vertices." %
                        (aob.name, aob.data.DazVertexCount, cob.name, ncverts))
                raise DazError(msg)

        cname = self.getUvName(cob.data)
        anames = []
        drivers = {}

        # Keep extra UVs
        self.keepUv = []
        for ob in [cob] + anatomies:
            for uvtex in getUvTextures(ob.data):
                if not uvtex.active_render:
                    self.keepUv.append(uvtex.name)

        # Select graft group for each anatomy
        for aob in anatomies:
            activateObject(context, aob)
            self.moveGraftVerts(aob, cob)
            getShapekeyDrivers(aob, drivers)
            for uvtex in getUvTextures(aob.data):
                if uvtex.active_render:
                    anames.append(uvtex.name)
                else:
                    self.keepUv.append(uvtex.name)

        # For the body, setup mask groups
        activateObject(context, cob)
        nverts = len(cob.data.vertices)
        vfaces = dict([(vn,[]) for vn in range(nverts)]) # {0: [9337, 9346, 10746, 10755], 1: [9806, 9811, 11215, 11220], 2: [1685, 2398, 8644, 10053], 3: [2047, 2760, 9922, 11331], 4: [9156, 9157, 10565, 10566], 5: [9155, 9203, 10564, 10612], 6: [9154, 9155, 10563, 10564], 7: [9154, 9409, 10563, 10818], 8: [1978, 1986, 2691, 2699], 9: [1975, 1983, 2688, 2696], 10: [1978, 1980, 2691, 2693], 11: [1685, 2165, 2398, 2878], 12: [9158, 9169, 10567, 10578], 13: [3086, 3103, 3188, 3205], ...}
        for f in cob.data.polygons:                      # 0 is the vertex index, and 9337, 9346, 10746, 10755 are faces the 0 indexed vertex belongs to !!! (is not the other way around!!!)
            for vn in f.vertices:
                vfaces[vn].append(f.index) #we build vertex index array which holds all faces index that contains this vertex

        masked_array =[]  #added by me
        nfaces = len(cob.data.polygons)
        #fmasked is going to tell me which face is masked (which face index)
        fmasked = dict([(fn,False) for fn in range(nfaces)]) #we init as false first {0: False, 1: False, 2: False, 3: False, 4: False, 5: False, 6: False, 7: False, 8: False, 9: False, 10: False, 11: False, 12: False, 13: False, ...}
        for aob in anatomies:
            for face in aob.data.DazMaskGroup: # DazMaskGroup = hidden_polys
                fmasked[face.a] = True
                masked_array.append(face.a)

        print("masked array is:\n")
        print (str(masked_array)[1:-1]) 
        # If cob is itself a geograft, make sure to keep the boundary
        if cob.data.DazGraftGroup:
            cgrafts = [pair.a for pair in cob.data.DazGraftGroup]
        else:
            cgrafts = [] # but if cob is not a geograft, then cgrafts is emtpy

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        # Select body verts to delete
        vdeleted = dict([(vn,False) for vn in range(nverts)])
        for aob in anatomies:
            paired = [pair.b for pair in aob.data.DazGraftGroup]
            for face in aob.data.DazMaskGroup:  # for every hidden_face
                fverts = cob.data.polygons[face.a].vertices #face.a is the index of the hidden_face
                vdelete = []
                for vn in fverts: #this is an actually _for_loop_ for every vertex that belongs to a face that is a hidden_face
                    if vn in cgrafts:
                        pass
                    elif vn not in paired: #if the vertex belongs to a hidden_face, but is not in vertex_pairs (common in both meshes)
                        vdelete.append(vn) # then we add it to the deletion list
                    else:
                        mfaces = [fn for fn in vfaces[vn] if fmasked[fn]] # this is a dictionary like vfaces, but only if is masked
                        if len(mfaces) == len(vfaces[vn]):                # so for a vertex (vn is the index) we look at adiacent faces and put all those faces in an array
                            vdelete.append(vn)                            # and if the mfaces (all faces adiacent to an index that are hidden_face-s) is the same as the all faces adiacent
                #                                                         # more exactly, in simple translate, if all faces adiacent to a vertex are also hidden
                #                                                         # then we add that vertex index to the deletion list
                for vn in vdelete:                         
                    cob.data.vertices[vn].select = True
                    vdeleted[vn] = True

        # Build association table between new and old vertex numbers
        assoc = {}  #when we delete the vertices, a remaining vertex takes the position of the deleted one, vertices index is shifted
        vn2 = 0     #so vn2 is the new vn vertex
        for vn in range(nverts):
            if not vdeleted[vn]:
                assoc[vn] = vn2
                vn2 += 1

        aobDazGraftGroupCounter = len (aob.data.DazGraftGroup)
        newVertexGroupPrefix = id_generator()+id_generator()+"_"
        for index,pair in enumerate(aob.data.DazGraftGroup):
            newVertexGroup = aob.vertex_groups.new(name=newVertexGroupPrefix+str(index))
            newVertexGroup.add([pair.a], 0.0, 'ADD')
            newVertexGroup = cob.vertex_groups.new(name=newVertexGroupPrefix+str(index))
            newVertexGroup.add([pair.b], 0.0, 'ADD')
        
        aobVerts = [v.index for v in aob.data.vertices]
        newVertexGroup = aob.vertex_groups.new(name=newVertexGroupPrefix+"all_vertices")
        newVertexGroup.add(aobVerts, 0.0, 'ADD')

        # Delete the masked verts
        bpy.ops.object.mode_set(mode='EDIT')
        #bpy.ops.mesh.delete(type='VERT')
        bpy.ops.object.mode_set(mode='OBJECT')

        # If cob is itself a geograft, store locations
        if cob.data.DazGraftGroup:
            verts = cob.data.vertices
            locations = dict([(pair.a, verts[pair.a].co.copy()) for pair in cob.data.DazGraftGroup])


        #hfg2 changes
        # first Select both graft and body and deselect vertices in edit mode
        # Select verts on common boundary
        names = []
        for aob in anatomies:
            setSelected(aob, True)
            names.append(aob.name)
        
        print("Merge %s to %s" % (names, cob.name))


        activateObject(context, cob)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        for aob in anatomies:
            activateObject(context, aob)
            setSelected(aob, True)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')

        activateObject(context, cob)
        setSelected(cob, True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        setSelected(aob, True)
        activateObject(context, cob)
        setSelected(aob, True)
        



        bpy.ops.object.join()
        
        # Deselect all verts
        bpy.ops.object.mode_set( mode = 'EDIT' )
        bpy.ops.mesh.select_all( action = 'DESELECT' )
        #bpy.ops.object.mode_set( mode = 'OBJECT' )
        #bpy.ops.object.mode_set(mode="EDIT")        
        #all vertex groups starts with newVertexGroupPrefix + +str(index)
        threshold = 0.001*cob.DazScale
        vgroups = cob.vertex_groups
        
        for index in range(aobDazGraftGroupCounter): # for index,notUsed in enumerate(aob.data.DazGraftGroup):
            print("Selecting indices for group: "+str(newVertexGroupPrefix+str(index)))
            vgroups.active_index = vgroups[newVertexGroupPrefix+str(index)].index
            bpy.ops.object.vertex_group_select()
            #bpy.ops.mesh.merge(type='CENTER', uvs=False)
            bpy.ops.mesh.remove_doubles(threshold=threshold)
            bpy.ops.object.vertex_group_deselect()
            #bpy.ops.mesh.select_all( action = 'DESELECT' )
            #bpy.ops.object.mode_set(mode='OBJECT')
            # Now the selected vertices are the ones that belong to this VG
            #vgVerts = [ v for v in o.data.vertices if v.select ]

            #   [vert for vert in cob.data.vertices if cob.vertex_groups[newVertexGroupPrefix+str(index)].index in [i.group for i in vert.groups]]
            # vg_idx = 0
            #o = bpy.context.object
            #vs = [ v for v in o.data.vertices if vg_idx in [ vg.group for vg in v.groups ] ]
        
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode="EDIT")

        for index in range(aobDazGraftGroupCounter): #for index,notUsed in enumerate(aob.data.DazGraftGroup):
            vgroups.active_index = vgroups[newVertexGroupPrefix+str(index)].index
            bpy.ops.object.vertex_group_select()
        vgroups.active_index = vgroups[newVertexGroupPrefix+"all_vertices"].index
        bpy.ops.object.vertex_group_select()

        #if 1==True:
        #    return {'FINISHED'}

        selected = dict([(v.index,v.co.copy()) for v in cob.data.vertices if v.select])

        bpy.ops.object.mode_set(mode='OBJECT')

        if True == False :
            #if 1==True:
            #    return {'FINISHED'}
            # ///////////////////////////////////////////////////////////// old code ///////////////////////////////////
            # Select nothing
            for aob in anatomies:
                activateObject(context, aob)
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='DESELECT')
                bpy.ops.object.mode_set(mode='OBJECT')
            activateObject(context, cob)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            # Select verts on common boundary
            names = []
            for aob in anatomies:
                setSelected(aob, True)
                names.append(aob.name)
                for pair in aob.data.DazGraftGroup:
                    aob.data.vertices[pair.a].select = True
                    if pair.b in assoc.keys():
                        cvn = assoc[pair.b]
                        cob.data.vertices[cvn].select = True
            
            
            # Also select cob graft group. These will not be removed.
            if cob.data.DazGraftGroup:
                for pair in cob.data.DazGraftGroup:
                    cvn = assoc[pair.a]
                    cob.data.vertices[cvn].select = True



            # Join meshes and remove doubles
            print("Merge %s to %s" % (names, cob.name))
            threshold = 0.001*cob.DazScale
            bpy.ops.object.join()
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.remove_doubles(threshold=threshold)
            bpy.ops.object.mode_set(mode='OBJECT')
            selected = dict([(v.index,v.co.copy()) for v in cob.data.vertices if v.select])
            bpy.ops.object.mode_set(mode='EDIT')
            if 1==True:
                return {'FINISHED'}
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')

        # Update cob graft group
        if cob.data.DazGraftGroup and selected:
            for pair in cob.data.DazGraftGroup:
                x = locations[pair.a]
                dists = [((x-y).length, vn) for vn,y in selected.items()]
                dists.sort()
                pair.a = dists[0][1]

        self.joinUvTextures(cob.data)

        #hfg2 cleanup merging groups, since we no longer need those we can remove them
        vgs = [vg for vg in cob.vertex_groups if vg.name.find(newVertexGroupPrefix) != -1]
        while(vgs):
            cob.vertex_groups.remove(vgs.pop())

        newname = self.getUvName(cob.data)
        for mat in cob.data.materials:
            if mat.use_nodes:
                replaceNodeNames(mat, cname, newname)
                for aname in anames:
                    replaceNodeNames(mat, aname, newname)

        # Remove unused materials
        self.mathits = dict([(mn,False) for mn in range(len(cob.data.materials))])
        for f in cob.data.polygons:
            self.mathits[f.material_index] = True
        self.mergeMaterials(cob)

        copyShapeKeyDrivers(cob, drivers)
        updateDrivers(cob)


    def keepMaterial(self, mn, mat, ob):
        keep = self.mathits[mn]
        if not keep:
            print("Remove material %s" % mat.name)
        return keep


    def moveGraftVerts(self, aob, cob):
        """ This function moves all common geograft vertices to the location of the coresponding vertices.\n It also `fixes` the vertices in shared shapekey names"""
        for pair in aob.data.DazGraftGroup:
            print("{0:d},{1:d}".format(pair.a,pair.b))
            aob.data.vertices[pair.a].co = cob.data.vertices[pair.b].co
        if cob.data.shape_keys and aob.data.shape_keys:
            for cskey in cob.data.shape_keys.key_blocks:
                if cskey.name in aob.data.shape_keys.key_blocks.keys():
                    askey = aob.data.shape_keys.key_blocks[cskey.name]
                    for pair in aob.data.DazGraftGroup:
                        askey.data[pair.a].co = cskey.data[pair.b].co


    def joinUvTextures(self, me):
        if len(me.uv_layers) <= 1:
            return
        for n,data in enumerate(me.uv_layers[0].data):
            if data.uv.length < 1e-6:
                for uvloop in me.uv_layers[1:]:
                    if uvloop.data[n].uv.length > 1e-6:
                        data.uv = uvloop.data[n].uv
                        break
        for uvtex in list(getUvTextures(me)[1:]):
            if uvtex.name not in self.keepUv:
                try:
                    getUvTextures(me).remove(uvtex)
                except RuntimeError:
                    print("Cannot remove texture layer '%s'" % uvtex.name)


    def getUvName(self, me):
        for uvtex in getUvTextures(me):
            if uvtex.active_render:
                return uvtex.name
        return None


def replaceNodeNames(mat, oldname, newname):
    texco = None
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_COORD':
            texco = node
            break

    uvmaps = []
    for node in mat.node_tree.nodes:
        if isinstance(node, bpy.types.ShaderNodeUVMap):
            if node.uv_map == oldname:
                node.uv_map = newname
                uvmaps.append(node)
        elif isinstance(node, bpy.types.ShaderNodeAttribute):
            if node.attribute_name == oldname:
                node.attribute_name = newname
        elif isinstance(node, bpy.types.ShaderNodeNormalMap):
            if node.uv_map == oldname:
                node.uv_map = newname

    if texco and uvmaps:
        fromsocket = texco.outputs["UV"]
        tosockets = []
        for link in mat.node_tree.links:
            if link.from_node in uvmaps:
                tosockets.append(link.to_socket)
        for tosocket in tosockets:
            mat.node_tree.links.new(fromsocket, tosocket)

    for node in uvmaps:
        mat.node_tree.nodes.remove(node)

#-------------------------------------------------------------
#   Create graft and mask vertex groups
#-------------------------------------------------------------

class DAZ_OT_CreateGraftGroups(DazOperator):
    bl_idname = "daz.create_graft_groups"
    bl_label = "Greate Graft Groups"
    bl_description = "Create vertex groups from graft information"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.DazGraftGroup)

    def run(self, context):
        aob = context.object
        objects = []
        for ob in getSceneObjects(context):
            if (ob.type == 'MESH' and
                getSelected(ob) and
                ob != aob):
                objects.append(ob)
        if len(objects) != 1:
            raise DazError("Exactly two meshes must be selected.    ")
        cob = objects[0]
        gname = "Graft_" + aob.data.name
        mname = "Mask_" + aob.data.name
        self.createVertexGroup(aob, gname, [pair.a for pair in aob.data.DazGraftGroup])
        graft = [pair.b for pair in aob.data.DazGraftGroup]
        self.createVertexGroup(cob, gname, graft)
        mask = {}
        for face in aob.data.DazMaskGroup:
            for vn in cob.data.polygons[face.a].vertices:
                if vn not in graft:
                    mask[vn] = True
        self.createVertexGroup(cob, mname, mask.keys())


    def createVertexGroup(self, ob, gname, vnums):
        vgrp = ob.vertex_groups.new(name=gname)
        for vn in vnums:
            vgrp.add([vn], 1, 'REPLACE')
        return vgrp

#-------------------------------------------------------------
#   Merge UV sets
#-------------------------------------------------------------

class DAZ_OT_MergeUVLayers(DazPropsOperator, IsMesh, B.MergeUVLayers):
    bl_idname = "daz.merge_uv_layers"
    bl_label = "Merge UV Layers"
    bl_description = "Merge two UV layers"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "layer1")
        self.layout.prop(self, "layer2")


    def run(self, context):
        me = context.object.data
        keepIdx = int(self.layer1)
        mergeIdx = int(self.layer2)
        if keepIdx == mergeIdx:
            raise DazError("Keep and merge UV layers are equal")
        keepLayer = me.uv_layers[keepIdx]
        mergeLayer = me.uv_layers[mergeIdx]
        for n,data in enumerate(mergeLayer.data):
            if data.uv.length > 1e-6:
                keepLayer.data[n].uv = data.uv

        for mat in me.materials:
            if mat.use_nodes:
                replaceNodeNames(mat, mergeLayer.name, keepLayer.name)

        if bpy.app.version < (2,80,0):
            me.uv_textures.active_index = keepIdx
            me.uv_textures.remove(me.uv_textures[mergeIdx])
        else:
            me.uv_layers.active_index = keepIdx
            me.uv_layers.remove(mergeLayer)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        print("UV layers joined")

#-------------------------------------------------------------
#   Get selected rigs
#-------------------------------------------------------------

def getSelectedRigs(context):
    rig = context.object
    if rig:
        bpy.ops.object.mode_set(mode='OBJECT')
    subrigs = []
    for ob in getSceneObjects(context):
        if getSelected(ob) and ob.type == 'ARMATURE' and ob != rig:
            subrigs.append(ob)
    return rig, subrigs

#-------------------------------------------------------------
#   Copy poses
#-------------------------------------------------------------

class DAZ_OT_CopyPoses(DazOperator, IsArmature):
    bl_idname = "daz.copy_poses"
    bl_label = "Copy Poses"
    bl_description = "Copy selected rig poses to active rig"
    bl_options = {'UNDO'}

    def run(self, context):
        rig,subrigs = getSelectedRigs(context)
        if rig is None:
            print("No poses to copy")
            return

        print("Copy pose to %s:" % rig.name)
        for ob in subrigs:
            print("  ", ob.name)
            if not setActiveObject(context, rig):
                continue

            # L_b = R^-1_b R_p M^-1_p M_b
            for cb in ob.pose.bones:
                if cb.name in rig.pose.bones:
                    pb = rig.pose.bones[cb.name]
                    mat = cb.matrix.copy()
                    mat.col[3] = pb.matrix.col[3]
                    mat = Mult2(ob.matrix_world.inverted(), mat)
                    par = pb.parent
                    if par:
                        mat = Mult3(par.bone.matrix_local, par.matrix.inverted(), mat)
                    mat = Mult2(pb.bone.matrix_local.inverted(), mat)
                    pb.matrix_basis = mat
                    toggleEditMode()

        setActiveObject(context, rig)

#-------------------------------------------------------------
#   Merge rigs
#-------------------------------------------------------------

class DAZ_OT_EliminateEmpties(DazOperator, IsArmature):
    bl_idname = "daz.eliminate_empties"
    bl_label = "Eliminate Empties"
    bl_description = "Delete empties with mesh children, parenting the meshes to the rig instead"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        deletes = []
        for empty in rig.children:
            if empty.type == 'EMPTY' and not isDuplicated(empty):
                for ob in empty.children:
                    if ob.type == 'MESH':
                        deletes.append(empty)
                        wmat = ob.matrix_world.copy()
                        if empty.parent_type == 'OBJECT':
                            ob.parent = rig
                            ob.parent_type = 'OBJECT'
                            ob.matrix_world = wmat
                        elif empty.parent_type == 'BONE':
                            bone = rig.data.bones[empty.parent_bone]
                            ob.parent = rig
                            ob.parent_type = 'BONE'
                            ob.parent_bone = empty.parent_bone
                            ob.matrix_world = wmat
                        else:
                            raise DazError("Unknown parent type: %s %s" % (ob.name, empty.parent_type))

        for empty in deletes:
            deleteObject(context, empty)


def isDuplicated(ob):
    if bpy.app.version < (2,80,0):
        return (ob.dupli_type != 'NONE')
    else:
        return (ob.instance_type != 'NONE')


class DAZ_OT_MergeRigs(DazPropsOperator, IsArmature, B.MergeRigs):
    bl_idname = "daz.merge_rigs"
    bl_label = "Merge Rigs"
    bl_description = "Merge selected rigs to active rig"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "clothesLayer")
        self.layout.prop(self, "useApplyRestPose")


    def run(self, context):
        rig,subrigs = getSelectedRigs(context)
        LS.forAnimation(None, rig, context.scene)
        if rig is None:
            raise DazError("No rigs to merge")
        oldvis = list(rig.data.layers)
        rig.data.layers = 32*[True]
        success = False
        try:
            if self.useApplyRestPose:
                applyRestPoses(context, rig, subrigs)
            self.mergeRigs(rig, subrigs, context)
            success = True
        finally:
            rig.data.layers = oldvis
            if success:
                rig.data.layers[self.clothesLayer-1] = True
            setActiveObject(context, rig)


    def mergeRigs(self, rig, subrigs, context):
        from .proxy import stripName
        from .node import clearParent, reParent
        scn = context.scene

        print("Merge rigs to %s:" % rig.name)
        bpy.ops.object.mode_set(mode='OBJECT')

        adds = []
        hdadds = []
        removes = []
        mcoll = hdcoll = None
        if bpy.app.version < (2,80,0):
            for grp in bpy.data.groups:
                if rig.name in grp.objects:
                    adds.append(grp)
        else:
            for coll in bpy.data.collections:
                if rig in coll.objects.values():
                    if coll.name.endswith("HD"):
                        if hdcoll is None:
                            hdcoll = bpy.data.collections.new(name= rig.name + " Meshes_HD")
                            hdadds = [hdcoll]
                        coll.children.link(hdcoll)
                    else:
                        if mcoll is None:
                            mcoll = bpy.data.collections.new(name= rig.name + " Meshes")
                            adds = [mcoll]
                        coll.children.link(mcoll)
                    removes.append(coll)

        for ob in rig.children:
            if ob.type == 'MESH':
                self.changeArmatureModifier(ob, rig, context)
                self.addToGroups(ob, adds, hdadds, removes)
            elif ob.type == 'EMPTY':
                reParent(context, ob, rig)

        self.mainBones = [bone.name for bone in rig.data.bones]
        for subrig in subrigs:
            success = True
            if (subrig.parent and
                subrig.parent_type == 'BONE'):
                parbone = subrig.parent_bone
                clearParent(subrig)
            else:
                parbone = None

            if success:
                print("  ", subrig.name, parbone)
                storage = self.addExtraBones(subrig, rig, context, scn, parbone)

                for ob in subrig.children:
                    if ob.type == 'MESH':
                        self.changeArmatureModifier(ob, rig, context)
                        self.changeVertexGroupNames(ob, storage)
                        self.addToGroups(ob, adds, hdadds, removes)
                        ob.name = stripName(ob.name)
                        ob.data.name = stripName(ob.data.name)
                        ob.parent = rig
                    elif ob.type == 'EMPTY':
                        reParent(context, ob, rig)

                subrig.parent = None
                deleteObject(context, subrig)

        activateObject(context, rig)
        bpy.ops.object.mode_set(mode='OBJECT')


    def changeVertexGroupNames(self, ob, storage):
        for bname in storage.keys():
            if bname in ob.vertex_groups.keys():
                vgrp = ob.vertex_groups[bname]
                vgrp.name = storage[bname].realname


    def addToGroups(self, ob, adds, hdadds, removes):
        if ob.name.endswith("HD"):
            adders = hdadds
        else:
            adders = adds
        for grp in adders:
            if ob.name not in grp.objects:
                grp.objects.link(ob)
        for grp in removes:
            if ob.name in grp.objects:
                grp.objects.unlink(ob)


    def changeArmatureModifier(self, ob, rig, context):
        from .node import reParent
        reParent(context, ob, rig)
        if ob.parent_type != 'BONE':
            for mod in ob.modifiers:
                if mod.type == "ARMATURE":
                    mod.name = rig.name
                    mod.object = rig
                    return
            mod = ob.modifiers.new(rig.name, "ARMATURE")
            mod.object = rig
            mod.use_deform_preserve_volume = True


    def addExtraBones(self, ob, rig, context, scn, parbone):
        from .figure import copyBoneInfo
        extras = []
        for bone in ob.data.bones:
            if (bone.name not in self.mainBones or
                bone.name not in rig.data.bones.keys()):
                extras.append(bone.name)

        if extras:
            storage = {}
            activateObject(context, ob)
            try:
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            except RuntimeError:
                pass

            bpy.ops.object.mode_set(mode='EDIT')
            for bname in extras:
                eb = ob.data.edit_bones[bname]
                storage[bname] = EditBoneStorage(eb, None)
            bpy.ops.object.mode_set(mode='OBJECT')

            setActiveObject(context, rig)
            layers = (self.clothesLayer-1)*[False] + [True] + (32-self.clothesLayer)*[False]
            bpy.ops.object.mode_set(mode='EDIT')
            for bname in extras:
                eb = storage[bname].createBone(rig, storage, parbone)
                eb.layers = layers
                storage[bname].realname = eb.name
            bpy.ops.object.mode_set(mode='OBJECT')
            for bname in extras:
                bone = rig.data.bones[bname]
                copyBoneInfo(ob.data.bones[bname], bone)
                bone.layers[self.clothesLayer-1] = True
            return storage
        else:
            return {}

#-------------------------------------------------------------
#   Copy bone locations
#-------------------------------------------------------------

class DAZ_OT_CopyBones(DazOperator, IsArmature):
    bl_idname = "daz.copy_bones"
    bl_label = "Copy Bones"
    bl_description = "Copy selected rig bone locations to active rig"
    bl_options = {'UNDO'}

    def run(self, context):
        rig,subrigs = getSelectedRigs(context)
        if rig is None:
            raise DazError("No target armature")
        if not subrigs:
            raise DazError("No source armature")
        copyBones(context, rig, subrigs)


def copyBones(context, rig, subrigs):
    print("Copy bones to %s:" % rig.name)
    ebones = []
    for ob in subrigs:
        print("  ", ob.name)
        if not setActiveObject(context, ob):
            continue
        bpy.ops.object.mode_set(mode='EDIT')
        for eb in ob.data.edit_bones:
            ebones.append(EditBoneStorage(eb))
        bpy.ops.object.mode_set(mode='OBJECT')

    setActiveObject(context, rig)
    bpy.ops.object.mode_set(mode='EDIT')
    for storage in ebones:
        storage.copyBoneLocation(rig)
    bpy.ops.object.mode_set(mode='OBJECT')

#-------------------------------------------------------------
#   Apply rest pose
#-------------------------------------------------------------

class DAZ_OT_ApplyRestPoses(DazOperator, IsArmature):
    bl_idname = "daz.apply_rest_pose"
    bl_label = "Apply Rest Pose"
    bl_description = "Apply current pose at rest pose to selected rigs and children"
    bl_options = {'UNDO'}

    def run(self, context):
        rig,subrigs = getSelectedRigs(context)
        LS.forAnimation(None, rig, context.scene)
        applyRestPoses(context, rig, subrigs)


def applyRestPoses(context, rig, subrigs):
    rigs = [rig] + subrigs
    for subrig in rigs:
        for ob in subrig.children:
            if ob.type == 'MESH':
                setRestPose(ob, subrig, context)
        if not setActiveObject(context, subrig):
            continue
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.armature_apply()
    setActiveObject(context, rig)
    bpy.ops.object.mode_set(mode='OBJECT')


def setRestPose(ob, rig, context):
    from .node import setParent
    if not setActiveObject(context, ob):
        return
    setParent(context, ob, rig)
    if ob.parent_type == 'BONE' or ob.type != 'MESH':
        return

    if LS.fitFile:
        for mod in ob.modifiers:
            if mod.type == 'ARMATURE':
                mod.object = rig
    else:
        for mod in ob.modifiers:
            if mod.type == 'ARMATURE':
                mname = mod.name
                if ob.data.shape_keys:
                    if bpy.app.version < (2,90,0):
                        bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=mname)
                    else:
                        bpy.ops.object.modifier_apply_as_shapekey(modifier=mname)
                    skey = ob.data.shape_keys.key_blocks[mname]
                    skey.value = 1.0
                else:
                    bpy.ops.object.modifier_apply(modifier=mname)
        mod = ob.modifiers.new(rig.name, "ARMATURE")
        mod.object = rig
        mod.use_deform_preserve_volume = True
        nmods = len(ob.modifiers)
        for n in range(nmods-1):
            bpy.ops.object.modifier_move_up(modifier=mod.name)

#-------------------------------------------------------------
#   Merge toes
#-------------------------------------------------------------

""" GenesisToes = {
    "lFoot" : ["lMetatarsals"],
    "rFoot" : ["rMetatarsals"],
    "lToe" : ["lSmallToe1", "lSmallToe2", "lSmallToe3", "lSmallToe4",
              "lSmallToe1_2", "lSmallToe2_2", "lSmallToe3_2", "lSmallToe4_2"],
    "rToe" : ["rSmallToe1", "rSmallToe2", "rSmallToe3", "rSmallToe4",
              "rSmallToe1_2", "rSmallToe2_2", "rSmallToe3_2", "rSmallToe4_2"],
} """

GenesisToes = {
    "lFoot" : ["lMetatarsals"],
    "rFoot" : ["rMetatarsals"],
    "lToe" : ["lBigToe", "lSmallToe1", "lSmallToe2", "lSmallToe3", "lSmallToe4",
              "lBigToe_2", "lSmallToe1_2", "lSmallToe2_2", "lSmallToe3_2", "lSmallToe4_2"],
    "rToe" : ["rBigToe", "rSmallToe1", "rSmallToe2", "rSmallToe3", "rSmallToe4",
              "rBigToe_2", "rSmallToe1_2", "rSmallToe2_2", "rSmallToe3_2", "rSmallToe4_2"],
}

NewParent = {
    "lToe" : "lFoot",
    "rToe" : "rFoot",
}


def reparentToes(rig, context):
    setActiveObject(context, rig)
    bpy.ops.object.mode_set(mode='EDIT')
    for parname in ["lToe", "rToe"]:
        if parname in rig.data.edit_bones.keys():
            parb = rig.data.edit_bones[parname]
            for bname in GenesisToes[parname]:
                if bname[-2:] == "_2":
                    continue
                if bname in rig.data.edit_bones.keys():
                    eb = rig.data.edit_bones[bname]
                    eb.parent = parb
    bpy.ops.object.mode_set(mode='OBJECT')


class DAZ_OT_ReparentToes(DazOperator, IsArmature):
    bl_idname = "daz.reparent_toes"
    bl_label = "Reparent Toes"
    bl_description = "Parent small toes to big toe bone"
    bl_options = {'UNDO'}

    def run(self, context):
        reparentToes(context.object, context)


def mergeBonesAndVgroups(rig, mergers, parents, context): # parents = {'lToe': 'lFoot', 'rToe': 'rFoot'}
    from .driver import removeBoneDrivers

    activateObject(context, rig)

    bpy.ops.object.mode_set(mode='OBJECT')
    for bones in mergers.values(): 
        removeBoneDrivers(rig, bones) #bones are ['rBigToe', 'rSmallToe1', 'rSmallToe2', 'rSmallToe3', 'rSmallToe4', 'rBigToe_2', 'rSmallToe1_2', 'rSmallToe2_2', 'rSmallToe3_2', 'rSmallToe4_2'] / ['rMetatarsals'] / ['lBigToe', 'lSmallToe1', 'lSmallToe2', 'lSmallToe3', 'lSmallToe4', 'lBigToe_2', 'lSmallToe1_2', 'lSmallToe2_2', 'lSmallToe3_2', 'lSmallToe4_2'] / ['lMetatarsals']




    bpy.ops.object.mode_set(mode='EDIT')
    for bname,pname in parents.items():
        if (pname in rig.data.edit_bones.keys() and
            bname in rig.data.edit_bones.keys()):
            eb = rig.data.edit_bones[bname]
            parb = rig.data.edit_bones[pname]
            eb.use_connect = False
            eb.parent = parb
            parb.tail = eb.head

    #modifiers = getattr(bpy.data.objects["Genesis 3 Female Mesh"], "modifiers", [])
    #modifiers[0].object = None


    for bones in mergers.values():
        for eb in rig.data.edit_bones:
            if eb.name in bones:
                #eb.name = eb.name+"_removed"
                rig.data.edit_bones.remove(eb)

    bpy.ops.object.mode_set(mode='OBJECT')

    #modifiers[0].object = bpy.data.objects['Genesis 3 Female']

    for ob in rig.children:
        if ob.type == 'MESH':
            for toe,subtoes in mergers.items():
                if toe in ob.vertex_groups.keys():
                    vgrp = ob.vertex_groups[toe]
                else:
                    vgrp = ob.vertex_groups.new(name=toe)
                subgrps = []
                for subtoe in subtoes:
                    if subtoe in ob.vertex_groups.keys():
                        subgrps.append(ob.vertex_groups[subtoe])
                idxs = [vg.index for vg in subgrps]
                idxs.append(vgrp.index)
                weights = dict([(vn,0) for vn in range(len(ob.data.vertices))])
                for v in ob.data.vertices:
                    for g in v.groups:
                        if g.group in idxs:
                            weights[v.index] += g.weight
                #for subgrp in subgrps:
                #    ob.vertex_groups.remove(subgrp)
                for vn,w in weights.items():
                    if w > 1e-3:
                        vgrp.add([vn], w, 'REPLACE')

    updateDrivers(rig)
    bpy.ops.object.mode_set(mode='OBJECT')


class DAZ_OT_MergeToes(DazOperator, IsArmature):
    bl_idname = "daz.merge_toes"
    bl_label = "Merge Toes"
    bl_description = "Merge all toes"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        mergeBonesAndVgroups(rig, GenesisToes, NewParent, context)

#-------------------------------------------------------------
#   EditBoneStorage
#-------------------------------------------------------------

class EditBoneStorage:
    def __init__(self, eb, pname=None):
        self.name = eb.name
        self.realname = self.name
        self.head = eb.head.copy()
        self.tail = eb.tail.copy()
        self.roll = eb.roll
        if eb.parent:
            self.parent = eb.parent.name
        else:
            self.parent = pname


    def createBone(self, rig, storage, parbone):
        eb = rig.data.edit_bones.new(self.name)
        self.realname = eb.name
        eb.head = self.head
        eb.tail = self.tail
        eb.roll = self.roll
        if storage and self.parent in storage.keys():
            pname = storage[self.parent].realname
        elif self.parent:
            pname = self.parent
        elif parbone:
            pname = parbone
        else:
            pname = None

        if pname is not None:
            eb.parent = rig.data.edit_bones[pname]
        return eb


    def copyBoneLocation(self, rig):
        if self.name in rig.data.edit_bones:
            eb = rig.data.edit_bones[self.name]
            eb.head = self.head
            eb.tail = self.tail
            eb.roll = self.roll

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MergeGeografts,
    DAZ_OT_MergeGeograftsFast,
    DAZ_OT_MergeGeograftsNonDestructive,
    DAZ_OT_CreateGraftGroups,
    DAZ_OT_MergeUVLayers,
    DAZ_OT_CopyPoses,
    DAZ_OT_MergeRigs,
    DAZ_OT_EliminateEmpties,
    DAZ_OT_CopyBones,
    DAZ_OT_ApplyRestPoses,
    DAZ_OT_ReparentToes,
    DAZ_OT_MergeToes,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
