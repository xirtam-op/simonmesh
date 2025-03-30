import re
import os
import numpy as np
from copy import deepcopy
import sys
import json
# import pyvista as pv

header = r'''
/*--------------------------------*- C++ -*----------------------------------*\
| =========                 |                                                 |
| \      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \    /   O peration     | Version:  v2312                                 |
|   \  /    A nd           | Website:  www.openfoam.com                      |
|    \/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      DICT;
}
// * * * * * * * * * * * * * modified by simonmesh * * * * * * * * * * * * * //
'''


class ToBoundary:
    def __init__(self, filename=None):
        self.boundaryName = filename
        self.res = ""
        
    def genBCFile(self, className, objName, varUnit, fieldType, fieldValue, bcList):
        self.assignHeader(className, objName)
        self.assignUnit(varUnit)
        self.assignInternalField(fieldType, fieldValue)
        self.assignBoundaryField(bcList)
        self.res += "//*************modified by sim.on.mesh********** //*\n"

        with open(self.boundaryName, "w") as f:
            f.write(self.res)
        
    def assignHeader(self, className, objName):
        global header
        local_header = re.sub(r'\bclass\s+dictionary\b', f'class    \t{className}', header)
        local_header = re.sub(r'\bobject\s+\w+\b', f'object    \t{objName}', local_header)
        self.res += local_header + '\n'
        
    def assignUnit(self, varUnit):
        self.res += 'dimensions\t[' + ' '.join([str(k) for k in varUnit]) + '];\n';
        
    def assignInternalField(self, fieldType, fieldValue):
        if len(fieldValue) == 1:
            self.res += 'internalField\t' + fieldType + '\t' + str(fieldValue[0]) + ';\n';
        else:
            self.res += 'internalField\t' + fieldType + '\t(' + ' '.join([str(k) for k in fieldValue]) + ');\n';
    
    def assignBoundaryField(self, bcList):
        self.res += 'boundaryField\n'
        self.res += '{\n'
        
        for bc in bcList:
            bcName, bcType, *bcInfo = bc
            print('bc: ', bcName, bcType, bcInfo)

            self.res += self.assignVar(bcName, bcType, bcInfo)
        self.res += '}\n'
        
    def assignVar(self, bcName, bcType, bcInfo):
        # {“name”: bcName, "type":fixedValue, "value": "uniform", "data": [0, 0, 0]}
        res = f'\t{bcName}\n'
        res += '\t{\n'
        res += '\t\ttype' + f'\t{bcType};\n'
        if len(bcInfo) == 0:
            res += '\t}\n'
            return res
        bcInfo = bcInfo[0]
        for k, v in bcInfo.items():
            if k == "data":
                res += f'\t\t'
                if len(v) > 1:
                    res += '('
                    res += ' '.join([str(j) for j in v])
                    res += ');\n'
                else:
                    res += f'\t\t{v[0]};\n'
            else:
                res += f'\t\t{k}\t{v}'

        res += '\t}\n'
                    
        return res
        
class ToMeshDICT:
    def __init__(self, mesh, fileName="sample/system/blockMeshDict"):
        self.obj = json.loads(mesh.getObj())
        self.filename = fileName
        self.num2Node_ = {}

        res = ""
        res += self.genHeader()
        res += self.genPrescale()
        res += self.genTransform()
        res += self.genGeometry()
        res += self.genVertices()
        res += self.genBlocks()
        res += self.genEdges()
        res += self.genFaces()
        res += self.genDefaultPatch()
        res += self.genBoundary()
        res += '// ************************************************************************* //\n'
        self.res = res
        
    def write(self):
        print('writeblockMeshDict: ', self.filename)
        with open(self.filename, "w") as f:
            f.write(self.res)
        

    def genHeader(self):
        nHeader = header.replace("DICT", "blockMeshDict")
        return nHeader
    
    def genPrescale(self):
        res_ = 'prescale (' + ' '.join([str(k) for k in self.obj['prescale']]) + ');\n'
        return res_

    def genPrescale(self):
        print('genPrescale: ', self.obj['prescale'])
        res_ = 'prescale (' + ' '.join([str(k) for k in self.obj['prescale']]) + ');\n'
        return res_

    def genTransform(self):
        if self.obj.get('transform') == None or len(self.obj['transform']) == 0:
            return '\n'
        res_ = 'transform\n{\n'
        
        for k, v in self.obj['transform'].items():
            if isinstance(v, list):
                v = [str(k) for k in v] 
                res_ += k + '    (' + ' '.join(v) + ');\n'
            else:
                res_ += k + '    ' + str(v) + ';\n'
        res_ += '}\n'
        return res_
        
    def genGeometry(self):
        if self.obj.get('geometry') == None or len(self.obj['geometry']) == 0:
            return '\n'
        res_ = 'geometry \n{\n'

        for k in self.obj['geometry']:
            '''
            res_ += '\t' + k + '\n'
            res_ += '\t{\n'
            for k_, v_ in self.obj['geometry'][k].items():   
                if isinstance(v_, list):
                    v_ = [str(j) for j in v_]
                    res_ += '\t\t' + k_ + '   (' + ' '.join(v_) + ');\n'
                else:
                    if k_ == 'type':
                        res_ += '\t\t' + k_ + '\t' + str(v_) + ';\n'
                    elif k_ == 'info':
                        for k__, v__ in v_.items():
                            strV__ = '(' + ' '.join([str(j) for j in v__]) + ')' if isinstance(v__, list)  else str(v__)
                            if k__ == 'file':
                                strV__ = '"' + strV__ + '"'
                            res_ += '\t\t' + k__ + '\t' + strV__ + ';\n' 
            res_ += '\t}\n'
            '''
            
            name_ = k["name"]
            type_ = k["type"]
            info_ = k["info"]
            print(name_, type_, info_)
            res_ += '\t' + name_ + '\n'
            res_ += '\t{\n'
            res_ += '\t\ttype\t' + type_ + ';\n'
            res_ += '\t\tfile\t' + name_ + '.stl;\n'
            res_ += '\t}\n'
            res_ += '\n'
            
        res_ += '}\n'
        return res_

    def genVertices(self):
        res_ = 'vertices\n(\n'
        for i, k_ in enumerate(self.obj['vertices']):
            res_ += '\t'
            
            if k_.get('project'):
                res_ += 'project (' + ' '.join([str(j) for j in k_.get('xyz')]) + ') (' + ' '.join(k_.get('project')) + ')\n'
            else:
                res_ += '(' + ' '.join([str(j) for j in k_.get('xyz')]) + ')\n'
        res_ += ');\n'
        return res_

    def genBlocks(self):
        res_ = 'blocks\n(\n'
        for i, b_ in enumerate(self.obj['blocks']):
            res_ += '\t'
            res_ += 'hex ('
            hex_ = []
            for n in b_.get('hex'):
                hex_.append(str(n))
            res_ += ' '.join(hex_)
            res_ += ') ('
            res_ += ' '.join([str(int(j)) for j in b_.get('number')])
            res_ += ') grading ('
            # res_ += ' '.join([str(j) for j in b_.get('grading')])
            # print('b_', b_.get("grading"))
            for j in b_.get("grading"):
                if len(j) == 1:
                    res_ += str(*j[0]) + ' '
                else:
                    res_ += '('
                    for z in j:
                        rZ = [z[1], z[0], z[2]]
                        res_ += '('
                        res_ += ' '.join([str(c_) for c_ in rZ])
                        res_ += ') '
                    if res_[-1] == ' ':
                        res_ = res_[:-1]
                    res_ += ') '
            if res_[-1] == ' ':
                res_ = res_[:-1]
            res_ += ')\n'
        res_ += ');\n'
        return res_
    
    def genEdges(self):
        print('edge', self.obj['edges'])
        res_ = 'edges\n(\n'
        for e_ in self.obj['edges']:

            res_ += '\t' + e_['type'] + ' '
            res_ += ' '.join([str(int(z)) for z in e_['vertices']])
            res_ += '\n\t(\n'
            for s_ in e_['points']:
                res_ += '\t('
                res_ += ' '.join([str(z) for z in s_])
                res_ += ')\n'
            res_ += '\t)\n'

        res_ += ');\n'
        return res_

    def genFaces(self):

        if self.obj.get('faces') == None or len(self.obj.get('faces')) == 0:
            return '\n'
        res_ = 'faces\n(\n'
        for f_ in self.obj['faces']:
            res_ += '\tproject ('
            res_ += ' '.join([str(z) for z in f_['indices']])
            res_ += ') ' + f_['project'] + '\n'    
        res_ += ');\n'
        return res_
    
    def genDefaultPatch(self):
        res_ = 'defaultPatch\n{\n'
        for k_, v_ in self.obj['defaultPatch'].items():
            res_ += '\t' + k_ + ' ' + v_ + ';\n'
        res_ += '}\n'
        return res_
    
    def genBoundary(self):
        print('genBoundary: ', self.obj['boundaries'])
        if self.obj.get('boundaries') == None or len(self.obj['boundaries']) == 0:
            return '\n'

        res_ = 'boundary\n(\n'
        for b_ in self.obj['boundaries']:
            print('patch: ', b_)
            name_ = b_["name"]
            res_ += '\t'+ name_ + '\n\t{\n'
            res_ += '\t\t' + 'type' + '\t' + b_["type"] + ';\n'
            res_ += '\t\t' + 'faces' + '\t('

            for j_ in b_["faces"]:
                res_ += '('
                res_ += ' '.join(str(z) for z in j_)
                res_ += ') '
            if res_[-1] == ' ':
                res_ = res_[:-1]
            res_ += ');\n'
            res_ += '\n\t}\n'
        
        res_ += ');\n'
        
        return res_
    '''
    def toPyVista(self):
        points = [v["xyz"] for v in self.obj["vertices"]]  

        num = 0
        cells = []
        for b in self.obj["blocks"]:
            hexCell = [v for v in b["hex"]]
            cells.append([8, *hexCell])
            num+=1
        cells = np.hstack(cells)
        
        bone_grid = pv.UnstructuredGrid(cells, np.full(num, pv.CellType.HEXAHEDRON, dtype=np.uint8), points)

        vertex_label = [f'{i["name"]}' for i in self.obj["vertices"]]

        # Function to toggle labels on or off
        return points, cells, bone_grid, vertex_label
    '''
    
class ToControlDICT:
    def __init__(self, filename="sample/system/controlDict"):
        self.filename = filename
        # self.genDict()
        res = ''
        res += header.replace("DICT", "controlDict")
        res += 'application     blockMesh;\n'
        res += 'startFrom       startTime;\n'
        res += 'startTime       0;\n'
        res += 'stopAt          endTime;\n'
        res += 'endTime         1000;\n'
        res += 'deltaT          1;\n'
        res += 'writeControl    timeStep;\n'
        res += 'writeInterval   1;\n'
        res += 'purgeWrite      0;\n'
        res += 'writeFormat     ascii;\n'
        res += 'writePrecision  6;\n'
        res += 'writeCompression off;\n'
        res += 'timeFormat      general;\n'
        res += 'timePrecision   6;\n'
        res += 'runTimeModifiable true;\n'
        res += '// ************************************************************************* //\n'
        self.res = res
        
    def genDict(self):
        res += ''
        
    def write(self):
        print('blockMeshDict: ', self.filename)
        with open(self.filename, "w") as f:
            f.write(self.res)
        
class ToMaterial:
    def __init__(self, filename="constant/transportProperties"):
        self.filename = filename
        self.res = ''
    
    def genDict(self):
        self.genHeader()
        self.genModel()
        self.genNu()
        self.res += '// **********************modified by simonmesh ********************* //\n'
    
        with open(self.filename, "w") as f:
            f.write(self.res)


    def genHeader(self, objName = "transportProperties"):
        global header
        # local_header = re.sub(r'\bclass\s+dictionary\b', f'class    \t{className}', header)
        local_header = re.sub(r'\bobject\s+\w+\b', f'object    \t{objName}', local_header)

    def genModel(self, modelType = "Newtonian"):
        self.res += f'transportModel\t{modelType};\n'
    
    def genNu(self, nu = 0.001, unit = [0, 2, -1, 0, 0, 0, 0]):
        self.res += f'nu\t{nu};\n'

class ToModel:
    def __init__(self, filename="constant/turbulenceProperties"):
        self.filename = filename
        self.res = ''

    def genHeader(self, objName = "turbulenceProperties"):
        global header
        # local_header = re.sub(r'\bclass\s+dictionary\b', f'class    \t{className}', header)
        local_header = re.sub(r'\bobject\s+\w+\b', f'object    \t{objName}', local_header)
        self.res += local_header + '\n'

    def genModel(self, modelType = "kEpsilon"):
        self.res += 'simulationType\t' + 'RAS' + ';\n'
        self.res += 'RAS\n{\n'
        self.res += '\t' + 'RASModel\t' + modelType + ';\n'
        self.res += '\t' + 'turbulence\t' + 'on' + ';\n'
        self.res += '\t' + 'printCoeffs\t' + 'on' + ';\n'
        self.res += '}\n'

    def genDict(self):
        self.genHeader()
        self.genModel()
        self.res += '// **********************modified by simonmesh ********************* //\n'
        with open(self.filename, "w") as f:
            f.write(self.res)

class ToSchemes:
    def __init__(self, filename="system/fvSchemes"):
        self.filename = filename
        self.res = ''

    def genDict(self):
        self.genHeader()
        self.genDDT()
        self.gradScheme()
        self.divScheme()
        self.laplacianScheme()
        self.interpolationScheme()
        self.snGradScheme()
        self.wallDist()
        self.res += '// **********************modified by simonmesh ********************* //\n'
        with open(self.filename, "w") as f:
            f.write(self.res)

    def genHeader(self, objName = "fvSchemes"):
        global header
        # local_header = re.sub(r'\bclass\s+dictionary\b', f'class    \t{className}', header)
        local_header = re.sub(r'\bobject\s+\w+\b', f'object    \t{objName}', local_header)
        self.res += local_header + '\n'

    def genDDT(self, ddtScheme = "Euler"):
        self.res += 'ddtSchemes\n{\n'
        self.res += '\t' + 'default\t' + ddtScheme + ';\n'
        self.res += '}\n'

    def gradScheme(self, gradScheme = "Gauss linear"):
        self.res += 'gradSchemes\n{\n'
        self.res += '\t' + 'default\t' + gradScheme + ';\n'
        self.res += '}\n'

    def divScheme(self, divScheme = "Gauss linear"):
        self.res += 'divSchemes\n{\n'
        self.res += '\t' + 'default\t' + divScheme + ';\n'
        self.res += '}\n'

    def laplacianScheme(self, laplacianScheme = "Gauss linear corrected"):
        self.res += 'laplacianSchemes\n{\n'
        self.res += '\t' + 'default\t' + laplacianScheme + ';\n'
        self.res += '}\n'

    def interpolationScheme(self, interpolationScheme = "linear"):
        self.res += 'interpolationSchemes\n{\n'
        self.res += '\t' + 'default\t' + interpolationScheme + ';\n'
        self.res += '}\n'

    def snGradScheme(self, snGradScheme = "corrected"):
        self.res += 'snGradSchemes\n{\n'
        self.res += '\t' + 'default\t' + snGradScheme + ';\n'
        self.res += '}\n'

    def wallDist(self, wallDist = "meshWave"):
        self.res += 'wallDist\n{\n'
        self.res += '\t' + 'method\t' + wallDist + ';\n'
        self.res += '}\n'

class ToSolution:
    def __init__(self, fileName):
        self.fileName = fileName
        self.res = ''

    def genHeader(self, objName = "fvSolution"):
        global header
        # local_header = re.sub(r'\bclass\s+dictionary\b', f'class    \t{className}', header)
        local_header = re.sub(r'\bobject\s+\w+\b', f'object    \t{objName}', local_header)
        self.res += local_header + '\n'

    def genSolvers(self, solvers):
        self.res += 'solvers\n{\n'
        for s in solvers:
            self.res += '\t' + s + '\n'
        self.res += '}\n'

    def genVarSolver(self, varName, varInfo):
        return