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

#-------------------------------------------------------------
#   animation.py
#-------------------------------------------------------------

theImagedDefaults = ";*.png;*.jpeg;*.jpg;*.bmp"
theImageExtensions = ["png", "jpeg", "jpg", "bmp", "tif", "tiff"]

theDazExtensions = ["dsf", "duf"]
theDazUpcaseExtensions = [ext.upper() for ext in theDazExtensions]
theDazDefaults = ";".join(["*.%s" % ext for ext in theDazExtensions+theDazUpcaseExtensions])

#-------------------------------------------------------------
#   convert.py
#-------------------------------------------------------------

theRestPoseFolder = os.path.join(os.path.dirname(__file__), "data", "restposes")
theParentsFolder = os.path.join(os.path.dirname(__file__), "data", "parents")
theIkPoseFolder = os.path.join(os.path.dirname(__file__), "data", "ikposes")

theRestPoseItems = []
for file in os.listdir(theRestPoseFolder):
    fname = os.path.splitext(file)[0]
    name = fname.replace("_", " ").capitalize()
    theRestPoseItems.append((fname, name, name))

#-------------------------------------------------------------
#   hide.py
#-------------------------------------------------------------

def getActiveMesh(scn, context):
    enums = []
    for ob in context.object.children:
        if ob.type == 'MESH':
            enums.append((ob.name, ob.name, ob.name))
    return enums

#-------------------------------------------------------------
#   morphing.py
#-------------------------------------------------------------

def getActiveCategories(scn, context):
    from .morphing import getRigFromObject
    rig = getRigFromObject(context.object)
    cats = [(cat.name,cat.name,cat.name) for cat in rig.DazMorphCats]
    cats.sort()
    return [("All", "All", "All")] + cats

#-------------------------------------------------------------
#   transfer.py
#-------------------------------------------------------------

def shapekeyItems1(self, context):
    filter = self.filter1.lower()
    return [(sname,sname,sname)
            for sname in context.object.data.shape_keys.key_blocks.keys()[1:]
            if filter in sname.lower()
           ]


def shapekeyItems2(self, context):
    filter = self.filter2.lower()
    enums = [(sname,sname,sname)
              for sname in context.object.data.shape_keys.key_blocks.keys()[1:]
              if filter in sname.lower()
            ]
    return [("-", "-", "None")] + enums
