import numpy as np

CONFIG = {
    'Opal1k': {
        'model': "Adimec",
        'manufacturer': "1000m/CL",
        'shape': (1024, 1024, 12),
        'size': 2
    },
    'Pulnix' : {
        'model': 'TM6740CL',
        'manufacturer': 'PULNIX',
        'shape': (480, 640, 10),
        'size': 2
    },
    'Visar' : {
        'model': 'C7700',
        'manufacturer': 'Hamamatsu',
        'shape': (1024, 1344, 16),
        'size': 2,
        'extra': {
            'ScaleX_RBV' : {
                'type': 'float',
                'value': 1e-7,
                'autosave' : True,
            },
            'ScaleY_RBV' : {
                'type': 'float',
                'value': 1.0,
                'autosave' : True,
            },
            'TimeRange_RBV' : {
                'type': 'enum',
                'enums': [
                    '0.5 ns',
                    '1 ns',
                    '2 ns',
                    '5 ns',
                    '10 ns',
                    '20 ns',
                    '50 ns',
                    '100 ns',
                    '200 ns',
                    '500 ns',
                    '1 us',
                    '2 us',
                    '5 us',
                    '10 us',
                    '20 us',
                    '50 us',
                ],
                'value': 0,
                'autosave' : True,
            },
            'TriggerMode_RBV' : {
                'type': 'enum',
                'enums': ['Focus', 'Operate'],
                'value': 0,
                'autosave' : True,
            },
            'GateMode_RBV' : {
                'type': 'enum',
                'enums': ['Normal', 'Gate', 'Open Fixed'],
                'value': 0,
                'autosave' : True,
            },
            'Shutter_RBV' : {
                'type': 'enum',
                'enums': ['Closed', 'Open'],
                'value': 0,
                'autosave' : True,
            },
            'ImageMode_RBV' : {
                'type': 'enum',
                'enums': ['Single', 'Continuous'],
                'value': 0,
                'autosave' : True,
            },
            'FocusTimeOver_RBV' : {
                'type': 'int',
                'value': 5,
                'autosave' : True,
            },
            'ScalingFilePath' : {
                'type': 'char',
                'count': 10000,
                'value': '/reg/neh/home/joaoprod/visar/mec/visar/current/VISAR1.txt',
                'autosave' : True,
            },
        },
    },
}

def get_max_array_size(camtype):
    size = 0x10000
    if camtype in CONFIG:
        height, width, _ = CONFIG[camtype]['shape']
        size += height * width * CONFIG[camtype]['size']
    else:
        size = 40000000

    return size

def get_dtype(camtype):
    if camtype in CONFIG:
        size = CONFIG[camtype]['size']
        if size <= 8:
            return np.uint8
        elif size <= 16:
            return np.uint16
        else:
            return np.uint32
    else:
        return np.uint16

def init(camtype):
    if camtype in CONFIG:
        pvdb = init_base(
            CONFIG[camtype]['manufacturer'],
            CONFIG[camtype]['model'],
            *CONFIG[camtype]['shape']
        )
        extras = CONFIG[camtype].get('extra', None)
        if extras is not None:
            pvdb.update(extras)
    else:
        pvdb = None
    
    return pvdb

def init_base(manufacturer, model, nrows, ncols, nbits):
    pvdb = {
    'FIDUCIAL': {
        'type': 'int',
        'value': 0xDEADBEEF,
        'readonly' : True,
    },
    'IMAGE1:ArrayData.NORD': {
        'type': 'int',
        'value': nrows * ncols,
        'readonly' : True,
    },
    'IMAGE1:ArrayData': {
        'type': 'short',
        'count': nrows * ncols,
        'readonly' : True,
    },
    'IMAGE1:ArraySize1_RBV': {
        'type': 'int',
        'value': nrows,
        'readonly' : True,
    },
    'IMAGE1:ArraySize0_RBV': {
        'type': 'int',
        'value': ncols,
        'readonly' : True,
    },
    'IMAGE1:BitsPerPixel_RBV': {
        'type': 'int',
        'value': nbits,
        'readonly' : True,
    },
    'Model_RBV': {
        'type': 'string',
        'value': model,
        'readonly' : True,
    },
    'Manufacturer_RBV': {
        'type': 'string',
        'value': manufacturer,
        'readonly' : True,
    },
    'MinX_RBV' :{
        'type': 'int',
        'value': 0,
        'autosave' : True,
    },
    'MinY_RBV' :{
        'type': 'int',
        'value': 0,
        'autosave' : True,
    },
    'SizeX_RBV' :{
        'type': 'int',
        'value': nrows,
        'autosave' : True,
    },
    'SizeY_RBV' :{
        'type': 'int',
        'value': ncols,
        'autosave' : True,
    },
    'AcquireTime_RBV' :{
        'type': 'float',
        'value': 0.0,
        'autosave' : True,
    },
    'Gain_RBV' :{
        'type': 'float',
        'value': 0.0,
        'autosave' : True,
    },
    'READOUT': {
        'type': 'int',
        'value': 0,
        'readonly': True,
    },
    'PLATFORM': {
        'type': 'int',
        'value': 0,
        'readonly': True,
    },
    'TIMEOUT': {
        'type': 'float',
        'value': 5.0,
        'autosave' : True,
    },
    'OFFSET': {
        'type': 'int',
        'value': 100,
        'autosave': True,
    },
    'SCALE': {
        'type': 'int',
        'value': 10,
        'autosave': True,
    }
    }

    return pvdb
