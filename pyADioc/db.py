def init(camtype):
    if camtype == 'Opal1k':
        pvdb = init_base("Adimec", "1000m/CL", 1024, 1024, 12)
    elif camtype == 'Pulnix':
        pvdb = init_base("Adimec", "1000m/CL", 480, 640, 10)
    elif camtype == 'Visar':
        pvdb = init_base("Hamamatsu", "CC7700", 1024, 1344, 16)
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
