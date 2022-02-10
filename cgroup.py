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

from .cycles import CyclesTree
from .pbr import PbrTree
from .material import WHITE

# ---------------------------------------------------------------------
#   CyclesGroup
# ---------------------------------------------------------------------

class MaterialGroup:
    def __init__(self, node, name, parent, ncols):
        self.group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
        node.node_tree = self.group
        self.nodes = self.group.nodes
        self.links = self.group.links
        self.inputs = self.addNode("NodeGroupInput", 0)
        self.outputs = self.addNode("NodeGroupOutput", ncols)
        self.parent = parent
        self.ncols = ncols


class CyclesGroup(MaterialGroup, CyclesTree):
    def __init__(self, node, name, parent, ncols):
        CyclesTree.__init__(self, parent.material)
        MaterialGroup.__init__(self, node, name, parent, ncols)

    def __repr__(self):
        return ("<NodeGroup %s>" % self.group)

# ---------------------------------------------------------------------
#   Shell Group
# ---------------------------------------------------------------------

class ShellGroup(MaterialGroup):

    def __init__(self, node, name, parent):
        MaterialGroup.__init__(self, node, name, parent, 8)
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.inputs.new("NodeSocketVector", "UV")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")


    def addNodes(self, context, shell):
        shell.rna = self.parent.material.rna
        self.material = shell
        self.texco = self.inputs.outputs["UV"]
        self.buildLayer(context)
        alpha,tex = self.getColorTex("getChannelCutoutOpacity", "NONE", 1.0)
        self.addOutput(alpha, tex, self.getCyclesSocket(), "Cycles")
        self.addOutput(alpha, tex, self.getEeveeSocket(), "Eevee")


    def addOutput(self, alpha, tex, socket, slot):
        mix = self.addNode("ShaderNodeMixShader", 7)
        mix.inputs[0].default_value = alpha
        if tex:
            self.links.new(tex.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs[slot], mix.inputs[1])
        self.links.new(socket, mix.inputs[2])
        self.links.new(mix.outputs[0], self.outputs.inputs[slot])


class ShellCyclesGroup(ShellGroup, CyclesTree):
    def __init__(self, node, name, parent):
        CyclesTree.__init__(self, parent.material)
        ShellGroup.__init__(self, node, name, parent)


class ShellPbrGroup(ShellGroup, PbrTree):
    def __init__(self, node, name, parent):
        PbrTree.__init__(self, parent.material)
        ShellGroup.__init__(self, node, name, parent)


# ---------------------------------------------------------------------
#   Fresnel Group
# ---------------------------------------------------------------------

class FresnelGroup(CyclesGroup):

    def __init__(self, node, name, parent):
        CyclesGroup.__init__(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.group.outputs.new("NodeSocketFloat", "Fac")


    def addNodes(self, args=None):
        geo = self.addNode("ShaderNodeNewGeometry", 1)

        bump = self.addNode("ShaderNodeBump", 1)
        self.links.new(self.inputs.outputs["Normal"], bump.inputs["Normal"])
        bump.inputs["Strength"].default_value = 0

        mix1 = self.addNode("ShaderNodeMixRGB", 2)
        self.links.new(geo.outputs["Backfacing"], mix1.inputs["Fac"])
        self.links.new(self.inputs.outputs["IOR"], mix1.inputs[1])
        mix1.inputs[2].default_value[0:3] = WHITE

        mix2 = self.addNode("ShaderNodeMixRGB", 2)
        self.links.new(self.inputs.outputs["Roughness"], mix2.inputs["Fac"])
        self.links.new(bump.outputs[0], mix2.inputs[1])
        self.links.new(geo.outputs["Incoming"], mix2.inputs[2])

        fresnel = self.addNode("ShaderNodeFresnel", 3)
        self.links.new(mix1.outputs[0], fresnel.inputs["IOR"])
        self.links.new(mix2.outputs[0], fresnel.inputs["Normal"])
        self.links.new(fresnel.outputs["Fac"], self.outputs.inputs["Fac"])

# ---------------------------------------------------------------------
#   Mix Group. Mixes Cycles and Eevee
# ---------------------------------------------------------------------

class MixGroup(CyclesGroup):
    def __init__(self, node, name, parent, ncols):
        CyclesGroup.__init__(self, node, name, parent, ncols)
        self.group.inputs.new("NodeSocketFloat", "Fac")
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")


    def addNodes(self, args=None):
        self.mix1 = self.addNode("ShaderNodeMixShader", self.ncols-1)
        self.mix2 = self.addNode("ShaderNodeMixShader", self.ncols-1)
        self.links.new(self.inputs.outputs["Fac"], self.mix1.inputs[0])
        self.links.new(self.inputs.outputs["Fac"], self.mix2.inputs[0])
        self.links.new(self.inputs.outputs["Cycles"], self.mix1.inputs[1])
        self.links.new(self.inputs.outputs["Eevee"], self.mix2.inputs[1])
        self.links.new(self.mix1.outputs[0], self.outputs.inputs["Cycles"])
        self.links.new(self.mix2.outputs[0], self.outputs.inputs["Eevee"])

# ---------------------------------------------------------------------
#   Add Group. Adds to Cycles and Eevee
# ---------------------------------------------------------------------

class AddGroup(CyclesGroup):
    def __init__(self, node, name, parent, ncols):
        CyclesGroup.__init__(self, node, name, parent, ncols)
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")


    def addNodes(self, args=None):
        self.add1 = self.addNode("ShaderNodeAddShader", 2)
        self.add2 = self.addNode("ShaderNodeAddShader", 2)
        self.links.new(self.inputs.outputs["Cycles"], self.add1.inputs[0])
        self.links.new(self.inputs.outputs["Eevee"], self.add2.inputs[0])
        self.links.new(self.add1.outputs[0], self.outputs.inputs["Cycles"])
        self.links.new(self.add2.outputs[0], self.outputs.inputs["Eevee"])

# ---------------------------------------------------------------------
#   Emission Group
# ---------------------------------------------------------------------

class EmissionGroup(AddGroup):

    def __init__(self, node, name, parent):
        AddGroup.__init__(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Strength")


    def addNodes(self, args=None):
        AddGroup.addNodes(self, args)
        node = self.addNode("ShaderNodeEmission", 1)
        self.links.new(self.inputs.outputs["Color"], node.inputs["Color"])
        self.links.new(self.inputs.outputs["Strength"], node.inputs["Strength"])
        self.links.new(node.outputs[0], self.add1.inputs[1])
        self.links.new(node.outputs[0], self.add2.inputs[1])


class OneSidedGroup(CyclesGroup):
    def __init__(self, node, name, parent):
        CyclesGroup.__init__(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")

    def addNodes(self, args=None):
        geo = self.addNode("ShaderNodeNewGeometry", 1)
        trans = self.addNode("ShaderNodeBsdfTransparent", 1)
        mix1 = self.addNode("ShaderNodeMixShader", 2)
        mix2 = self.addNode("ShaderNodeMixShader", 2)
        self.links.new(geo.outputs["Backfacing"], mix1.inputs[0])
        self.links.new(geo.outputs["Backfacing"], mix2.inputs[0])
        self.links.new(self.inputs.outputs["Cycles"], mix1.inputs[1])
        self.links.new(self.inputs.outputs["Eevee"], mix2.inputs[1])
        self.links.new(trans.outputs[0], mix1.inputs[2])
        self.links.new(trans.outputs[0], mix2.inputs[2])
        self.links.new(mix1.outputs[0], self.outputs.inputs["Cycles"])
        self.links.new(mix1.outputs[0], self.outputs.inputs["Eevee"])

# ---------------------------------------------------------------------
#   Diffuse Group
# ---------------------------------------------------------------------

class DiffuseGroup(MixGroup):

    def __init__(self, node, name, parent):
        MixGroup.__init__(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        diffuse = self.addNode("ShaderNodeBsdfDiffuse", 1)
        self.links.new(self.inputs.outputs["Color"], diffuse.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], diffuse.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], diffuse.inputs["Normal"])
        self.links.new(diffuse.outputs[0], self.mix1.inputs[2])
        self.links.new(diffuse.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Glossy Group
# ---------------------------------------------------------------------

class GlossyGroup(MixGroup):

    def __init__(self, node, name, parent):
        MixGroup.__init__(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        glossy = self.addNode("ShaderNodeBsdfGlossy", 1)
        self.links.new(self.inputs.outputs["Color"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], glossy.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])
        self.links.new(glossy.outputs[0], self.mix1.inputs[2])
        self.links.new(glossy.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Refraction Group
# ---------------------------------------------------------------------

class RefractionGroup(MixGroup):

    def __init__(self, node, name, parent):
        MixGroup.__init__(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketColor", "Refraction Color")
        self.group.inputs.new("NodeSocketFloat", "Refraction Roughness")
        self.group.inputs.new("NodeSocketFloat", "Refraction IOR")
        self.group.inputs.new("NodeSocketFloat", "Fresnel IOR")
        self.group.inputs.new("NodeSocketColor", "Glossy Color")
        self.group.inputs.new("NodeSocketFloat", "Glossy Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        fresnel = self.addGroup(FresnelGroup, "DAZ Fresnel", 1)
        refr = self.addNode("ShaderNodeBsdfRefraction", 1)
        glossy = self.addNode("ShaderNodeBsdfGlossy", 1)

        self.links.new(self.inputs.outputs["Refraction Color"], refr.inputs["Color"])
        self.links.new(self.inputs.outputs["Refraction Roughness"], refr.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Refraction IOR"], refr.inputs["IOR"])
        self.links.new(self.inputs.outputs["Normal"], refr.inputs["Normal"])

        self.links.new(self.inputs.outputs["Glossy Color"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs["Glossy Roughness"], glossy.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])

        self.links.new(self.inputs.outputs["Fresnel IOR"], fresnel.inputs["IOR"])
        self.links.new(self.inputs.outputs["Glossy Roughness"], fresnel.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])

        mix = self.addNode("ShaderNodeMixShader", 2)
        self.links.new(fresnel.outputs[0], mix.inputs[0])
        self.links.new(refr.outputs[0], mix.inputs[1])
        self.links.new(glossy.outputs[0], mix.inputs[2])

        self.links.new(mix.outputs[0], self.mix1.inputs[2])
        self.links.new(mix.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Transparent Group
# ---------------------------------------------------------------------

class TransparentGroup(MixGroup):

    def __init__(self, node, name, parent):
        MixGroup.__init__(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        trans = self.addNode("ShaderNodeBsdfTransparent", 1)
        self.links.new(self.inputs.outputs["Color"], trans.inputs["Color"])
        # Flip
        self.links.new(self.inputs.outputs["Cycles"], self.mix1.inputs[2])
        self.links.new(self.inputs.outputs["Eevee"], self.mix2.inputs[2])
        self.links.new(trans.outputs[0], self.mix1.inputs[1])
        self.links.new(trans.outputs[0], self.mix2.inputs[1])

# ---------------------------------------------------------------------
#   Translucent Group
# ---------------------------------------------------------------------

class TranslucentGroup(MixGroup):

    def __init__(self, node, name, parent):
        MixGroup.__init__(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Scale")
        self.group.inputs.new("NodeSocketVector", "Radius")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        trans = self.addNode("ShaderNodeBsdfTranslucent", 1)
        self.links.new(self.inputs.outputs["Color"], trans.inputs["Color"])
        self.links.new(self.inputs.outputs["Normal"], trans.inputs["Normal"])

        gamma = self.addNode("ShaderNodeGamma", 1)
        self.links.new(self.inputs.outputs["Color"], gamma.inputs["Color"])
        gamma.inputs["Gamma"].default_value = 2.5

        sss = self.addNode("ShaderNodeSubsurfaceScattering", 1)
        self.links.new(gamma.outputs["Color"], sss.inputs["Color"])
        self.links.new(self.inputs.outputs["Scale"], sss.inputs["Scale"])
        self.links.new(self.inputs.outputs["Radius"], sss.inputs["Radius"])
        self.links.new(self.inputs.outputs["Normal"], sss.inputs["Normal"])

        self.links.new(trans.outputs[0], self.mix1.inputs[2])
        self.links.new(sss.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   SSS Group
# ---------------------------------------------------------------------

class SSSGroup(MixGroup):

    def __init__(self, node, name, parent):
        MixGroup.__init__(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Scale")
        self.group.inputs.new("NodeSocketVector", "Radius")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        sss = self.addNode("ShaderNodeSubsurfaceScattering", 1)
        self.links.new(self.inputs.outputs["Color"], sss.inputs["Color"])
        self.links.new(self.inputs.outputs["Scale"], sss.inputs["Scale"])
        self.links.new(self.inputs.outputs["Radius"], sss.inputs["Radius"])
        self.links.new(self.inputs.outputs["Normal"], sss.inputs["Normal"])
        self.links.new(sss.outputs[0], self.mix1.inputs[2])
        self.links.new(sss.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Dual Lobe Group
# ---------------------------------------------------------------------

class DualLobeGroup(CyclesGroup):

    def __init__(self, node, name, parent):
        CyclesGroup.__init__(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketFloat", "Fac")
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.inputs.new("NodeSocketFloat", "Weight")
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.group.inputs.new("NodeSocketFloat", "Roughness 1")
        self.group.inputs.new("NodeSocketFloat", "Roughness 2")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")


    def addNodes(self, args=None):
        fresnel1 = self.addFresnel(True)
        glossy1 = self.addGlossy("Roughness 1", True)
        cycles1 = self.mixGlossy(fresnel1, glossy1, "Cycles")
        eevee1 = self.mixGlossy(fresnel1, glossy1, "Eevee")
        fresnel2 = self.addFresnel(False)
        glossy2 = self.addGlossy("Roughness 2", False)
        cycles2 = self.mixGlossy(fresnel2, glossy2, "Cycles")
        eevee2 = self.mixGlossy(fresnel2, glossy2, "Eevee")
        self.mixOutput(cycles1, cycles2, "Cycles")
        self.mixOutput(eevee1, eevee2, "Eevee")


    def addFresnel(self, useNormal):
        fresnel = self.addNode("ShaderNodeFresnel", 1)
        self.links.new(self.inputs.outputs["IOR"], fresnel.inputs["IOR"])
        if useNormal:
            self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])
        return fresnel


    def addGlossy(self, roughness, useNormal):
        glossy = self.addNode("ShaderNodeBsdfGlossy", 1)
        self.links.new(self.inputs.outputs["Weight"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs[roughness], glossy.inputs["Roughness"])
        if useNormal:
            self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])
        return glossy


    def mixGlossy(self, fresnel, glossy, slot):
        mix = self.addNode("ShaderNodeMixShader", 2)
        self.links.new(fresnel.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs[slot], mix.inputs[1])
        self.links.new(glossy.outputs[0], mix.inputs[2])
        return mix


    def mixOutput(self, node1, node2, slot):
        mix = self.addNode("ShaderNodeMixShader", 3)
        self.links.new(self.inputs.outputs["Fac"], mix.inputs[0])
        self.links.new(node1.outputs[0], mix.inputs[2])
        self.links.new(node2.outputs[0], mix.inputs[1])
        self.links.new(mix.outputs[0], self.outputs.inputs[slot])

# ---------------------------------------------------------------------
#   Volume Group
# ---------------------------------------------------------------------

class VolumeGroup(CyclesGroup):

    def __init__(self, node, name, parent):
        CyclesGroup.__init__(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Absorbtion Color")
        self.group.inputs.new("NodeSocketFloat", "Absorbtion Density")
        self.group.inputs.new("NodeSocketColor", "Scatter Color")
        self.group.inputs.new("NodeSocketFloat", "Scatter Density")
        self.group.inputs.new("NodeSocketFloat", "Scatter Anisotropy")
        self.group.outputs.new("NodeSocketShader", "Volume")


    def addNodes(self, args=None):
        absorb = self.addNode("ShaderNodeVolumeAbsorption", 1)
        self.links.new(self.inputs.outputs["Absorbtion Color"], absorb.inputs["Color"])
        self.links.new(self.inputs.outputs["Absorbtion Density"], absorb.inputs["Density"])

        scatter = self.addNode("ShaderNodeVolumeScatter", 1)
        self.links.new(self.inputs.outputs["Scatter Color"], scatter.inputs["Color"])
        self.links.new(self.inputs.outputs["Scatter Density"], scatter.inputs["Density"])
        self.links.new(self.inputs.outputs["Scatter Anisotropy"], scatter.inputs["Anisotropy"])

        volume = self.addNode("ShaderNodeAddShader", 2)
        self.links.new(absorb.outputs[0], volume.inputs[0])
        self.links.new(scatter.outputs[0], volume.inputs[1])
        self.links.new(volume.outputs[0], self.outputs.inputs["Volume"])

# ---------------------------------------------------------------------
#   Normal Group
#
#   https://blenderartists.org/t/way-faster-normal-map-node-for-realtime-animation-playback-with-tangent-space-normals/1175379
# ---------------------------------------------------------------------

class NormalGroup(CyclesGroup):

    def __init__(self, node, name, parent):
        CyclesGroup.__init__(self, node, name, parent, 8)

        strength = self.group.inputs.new("NodeSocketFloat", "Strength")
        strength.default_value = 1.0
        strength.min_value = 0.0
        strength.max_value = 1.0

        color = self.group.inputs.new("NodeSocketColor", "Color")
        color.default_value = ((0.5, 0.5, 1.0, 1.0))

        self.group.outputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args):
        # Generate TBN from Bump Node
        frame = self.nodes.new("NodeFrame")
        frame.label = "Generate TBN from Bump Node"

        uvmap = self.addNode("ShaderNodeUVMap", 1, parent=frame)
        if args[0]:
            uvmap.uv_map = args[0]

        uvgrads = self.addNode("ShaderNodeSeparateXYZ", 2, label="UV Gradients", parent=frame)
        self.links.new(uvmap.outputs["UV"], uvgrads.inputs[0])

        tangent = self.addNode("ShaderNodeBump", 3, label="Tangent", parent=frame)
        tangent.invert = True
        tangent.inputs["Distance"].default_value = 1
        self.links.new(uvgrads.outputs[0], tangent.inputs["Height"])

        bitangent = self.addNode("ShaderNodeBump", 3, label="Bi-Tangent", parent=frame)
        bitangent.invert = True
        bitangent.inputs["Distance"].default_value = 1000
        self.links.new(uvgrads.outputs[1], bitangent.inputs["Height"])

        geo = self.addNode("ShaderNodeNewGeometry", 3, label="Normal", parent=frame)

        # Transpose Matrix
        frame = self.nodes.new("NodeFrame")
        frame.label = "Transpose Matrix"

        sep1 = self.addNode("ShaderNodeSeparateXYZ", 4, parent=frame)
        self.links.new(tangent.outputs["Normal"], sep1.inputs[0])

        sep2 = self.addNode("ShaderNodeSeparateXYZ", 4, parent=frame)
        self.links.new(bitangent.outputs["Normal"], sep2.inputs[0])

        sep3 = self.addNode("ShaderNodeSeparateXYZ", 4, parent=frame)
        self.links.new(geo.outputs["Normal"], sep3.inputs[0])

        comb1 = self.addNode("ShaderNodeCombineXYZ", 5, parent=frame)
        self.links.new(sep1.outputs[0], comb1.inputs[0])
        self.links.new(sep2.outputs[0], comb1.inputs[1])
        self.links.new(sep3.outputs[0], comb1.inputs[2])

        comb2 = self.addNode("ShaderNodeCombineXYZ", 5, parent=frame)
        self.links.new(sep1.outputs[1], comb2.inputs[0])
        self.links.new(sep2.outputs[1], comb2.inputs[1])
        self.links.new(sep3.outputs[1], comb2.inputs[2])

        comb3 = self.addNode("ShaderNodeCombineXYZ", 5, parent=frame)
        self.links.new(sep1.outputs[2], comb3.inputs[0])
        self.links.new(sep2.outputs[2], comb3.inputs[1])
        self.links.new(sep3.outputs[2], comb3.inputs[2])

        # Normal Map Processing
        frame = self.nodes.new("NodeFrame")
        frame.label = "Normal Map Processing"

        rgb = self.addNode("ShaderNodeMixRGB", 3, parent=frame)
        self.links.new(self.inputs.outputs["Strength"], rgb.inputs[0])
        rgb.inputs[1].default_value = (0.5, 0.5, 1.0, 1.0)
        self.links.new(self.inputs.outputs["Color"], rgb.inputs[2])

        sub = self.addNode("ShaderNodeVectorMath", 4, parent=frame)
        sub.operation = 'SUBTRACT'
        self.links.new(rgb.outputs["Color"], sub.inputs[0])
        sub.inputs[1].default_value = (0.5, 0.5, 0.5)

        add = self.addNode("ShaderNodeVectorMath", 5, parent=frame)
        add.operation = 'ADD'
        self.links.new(sub.outputs[0], add.inputs[0])
        self.links.new(sub.outputs[0], add.inputs[1])

        # Matrix * Normal Map
        frame = self.nodes.new("NodeFrame")
        frame.label = "Matrix * Normal Map"

        dot1 = self.addNode("ShaderNodeVectorMath", 6, parent=frame)
        dot1.operation = 'DOT_PRODUCT'
        self.links.new(comb1.outputs[0], dot1.inputs[0])
        self.links.new(add.outputs[0], dot1.inputs[1])

        dot2 = self.addNode("ShaderNodeVectorMath", 6, parent=frame)
        dot2.operation = 'DOT_PRODUCT'
        self.links.new(comb2.outputs[0], dot2.inputs[0])
        self.links.new(add.outputs[0], dot2.inputs[1])

        dot3 = self.addNode("ShaderNodeVectorMath", 6, parent=frame)
        dot3.operation = 'DOT_PRODUCT'
        self.links.new(comb3.outputs[0], dot3.inputs[0])
        self.links.new(add.outputs[0], dot3.inputs[1])

        comb = self.addNode("ShaderNodeCombineXYZ", 7, parent=frame)
        self.links.new(dot1.outputs["Value"], comb.inputs[0])
        self.links.new(dot2.outputs["Value"], comb.inputs[1])
        self.links.new(dot3.outputs["Value"], comb.inputs[2])

        self.links.new(comb.outputs[0], self.outputs.inputs["Normal"])

# ---------------------------------------------------------------------
#   Displacement Group
# ---------------------------------------------------------------------

class DisplacementGroup(CyclesGroup):

    def __init__(self, node, name, parent):
        CyclesGroup.__init__(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketFloat", "Texture")
        self.group.inputs.new("NodeSocketFloat", "Strength")
        self.group.inputs.new("NodeSocketFloat", "Difference")
        self.group.inputs.new("NodeSocketFloat", "Min")
        self.group.outputs.new("NodeSocketFloat", "Height")


    def addNodes(self, args=None):
        mult1 = self.addNode("ShaderNodeMath", 1)
        mult1.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Texture"], mult1.inputs[0])
        self.links.new(self.inputs.outputs["Difference"], mult1.inputs[1])

        add = self.addNode("ShaderNodeMath", 2)
        add.operation = 'ADD'
        self.links.new(mult1.outputs[0], add.inputs[0])
        self.links.new(self.inputs.outputs["Min"], add.inputs[1])

        mult2 = self.addNode("ShaderNodeMath", 3)
        mult2.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Strength"], mult2.inputs[0])
        self.links.new(add.outputs[0], mult2.inputs[1])

        self.links.new(mult2.outputs[0], self.outputs.inputs["Height"])

# ---------------------------------------------------------------------
#   LIE Group
# ---------------------------------------------------------------------

class LieGroup(CyclesGroup):

    def __init__(self, node, name, parent):
        CyclesGroup.__init__(self, node, name, parent, 6)
        self.group.inputs.new("NodeSocketVector", "Vector")
        self.texco = self.inputs.outputs[0]
        self.group.inputs.new("NodeSocketFloat", "Alpha")
        self.group.outputs.new("NodeSocketColor", "Color")


    def addTextureNodes(self, assets, maps, colorSpace):
        texnodes = []
        for idx,asset in enumerate(assets):
            texnode,isnew = self.addSingleTexture(3, asset, maps[idx], colorSpace)
            if isnew:
                innode = texnode
                mapping = self.mapTexture(asset, maps[idx])
                if mapping:
                    texnode.extension = 'CLIP'
                    self.links.new(mapping.outputs["Vector"], texnode.inputs["Vector"])
                    innode = mapping
                else:
                    self.setTexNode(asset.images[colorSpace].name, texnode, colorSpace)
                self.links.new(self.inputs.outputs["Vector"], innode.inputs["Vector"])
            texnodes.append([texnode])

        if texnodes:
            nassets = len(assets)
            for idx in range(1, nassets):
                map = maps[idx]
                if map.invert:
                    inv = self.addNode("ShaderNodeInvert", 4)
                    node = texnodes[idx][0]
                    self.links.new(node.outputs[0], inv.inputs["Color"])
                    texnodes[idx].append(inv)

            texnode = texnodes[0][-1]
            alphamix = self.addNode("ShaderNodeMixRGB", 6)
            alphamix.blend_type = 'MIX'
            alphamix.inputs[0].default_value = 1.0
            self.links.new(self.inputs.outputs["Alpha"], alphamix.inputs[0])
            self.links.new(texnode.outputs["Color"], alphamix.inputs[1])

            masked = False
            for idx in range(1, nassets):
                map = maps[idx]
                if map.ismask:
                    if idx == nassets-1:
                        continue
                    mix = self.addNode("ShaderNodeMixRGB", 5)    # ShaderNodeMixRGB
                    mix.blend_type = 'MULTIPLY'
                    mix.use_alpha = False
                    mask = texnodes[idx][-1]
                    self.setColorSpace(mask, 'NONE')
                    self.links.new(mask.outputs["Color"], mix.inputs[0])
                    self.links.new(texnode.outputs["Color"], mix.inputs[1])
                    self.links.new(texnodes[idx+1][-1].outputs["Color"], mix.inputs[2])
                    texnode = mix
                    masked = True
                elif not masked:
                    mix = self.addNode("ShaderNodeMixRGB", 5)
                    alpha = setMixOperation(mix, map)
                    mix.inputs[0].default_value = alpha
                    node = texnodes[idx][-1]
                    base = texnodes[idx][0]
                    if alpha != 1:
                        node = self.multiplyScalarTex(alpha, base, 4, "Alpha")
                        self.links.new(node.outputs[0], mix.inputs[0])
                    elif "Alpha" in base.outputs.keys():
                        self.links.new(base.outputs["Alpha"], mix.inputs[0])
                    else:
                        print("No LIE alpha:", base)
                        mix.inputs[0].default_value = alpha
                    mix.use_alpha = True
                    self.links.new(texnode.outputs["Color"], mix.inputs[1])
                    self.links.new(texnodes[idx][-1].outputs["Color"], mix.inputs[2])
                    texnode = mix
                    masked = False
                else:
                    masked = False

            self.links.new(texnode.outputs[0], alphamix.inputs[2])
            self.links.new(alphamix.outputs[0], self.outputs.inputs["Color"])


    def mapTexture(self, asset, map):
        if asset.hasMapping(map):
            data = asset.getMapping(self.material, map)
            return self.addMappingNode(data, map)


def setMixOperation(mix, map):
    alpha = 1
    op = map.operation
    alpha = map.transparency
    if op == "multiply":
        mix.blend_type = 'MULTIPLY'
        useAlpha = True
    elif op == "add":
        mix.blend_type = 'ADD'
        useAlpha = False
    elif op == "subtract":
        mix.blend_type = 'SUBTRACT'
        useAlpha = False
    elif op == "alpha_blend":
        mix.blend_type = 'MIX'
        useAlpha = True
    else:
        print("MIX", asset, map.operation)
    return alpha
