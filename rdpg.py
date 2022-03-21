import dearpygui.dearpygui as dpg
from typing import Union, Any
from pathlib import Path
from ast import literal_eval

class TreeDict():

    def __init__(self, parent:Union[str,int], savename:str) -> None:
        self.parent = parent
        self.dict = {}
        self.f_lookup = {'input'     : {float : dpg.add_input_float,
                                        int   : dpg.add_input_int,
                                        str   : dpg.add_input_text,
                                        bool  : dpg.add_checkbox},
                         'drag'      : {float : dpg.add_drag_float,
                                        int   : dpg.add_drag_int},
                         'list'      : {float : dpg.add_input_floatx,
                                        int   : dpg.add_input_intx},
                         'list_drag' : {float : dpg.add_drag_floatx,
                                        int   : dpg.add_drag_intx}
                        }
        self.savefile = savename
        self.skip_save = []
        dpg.set_frame_callback(1,lambda _: self.load())


    def __getitem__(self, key):
        value = dpg.get_value(key)
        if value is None:
            raise ValueError(f"No value found in tree with {key}")
        return value

    def __setitem__(self,key,value):
        dpg.set_value(key,value)
    
    def add(self, name:str, value:Any, val_type:type = None, 
            order:int=1, drag:bool = False, save=True, callback = None,
            node_kwargs:dict = {}, item_kwargs:dict = {}):
        
        if callback is None:
            callback = self.get_save_callback()

        if not save:
            self.skip_save.append(name)

        hierarchy = name.split('/')
        layer_dict = self.dict
        # Traverse the hierarchy above the new item, creating
        # layers that don't already exist
        for i,layer in enumerate(hierarchy[:-1]):
            if layer not in layer_dict.keys():
                layer_dict[layer] = {}
                if i == 0:
                    parent = self.parent
                else:
                    parent = '/'.join(hierarchy[:i-1])
                node_dict = {'label' : layer,
                             'tag' : '/'.join(hierarchy[:1]),
                             'parent' : parent,
                             'default_open' : True}
                node_dict.update(node_kwargs)
                dpg.add_tree_node(**node_dict)
            layer_dict = layer_dict[layer]

        if hierarchy[-1] in layer_dict.keys():
            raise RuntimeError(f"{name} already exists in tree.")

        parent = '/'.join(hierarchy[:-1])
        layer_dict[hierarchy[-1]] = name

        # Autodetect type and order of object.
        if val_type is None:
            val_type = type(value)
            if val_type is list:
                val_type = type(value[0])
                if order == 1:
                    order = len(value)

        lookup = 'input'
        if drag:
            if order > 1:
                lookup = 'list_drag'
            else:
                lookup = 'drag'
        else:
            if order > 1:
                lookup = 'list'


        if order > 4:
            raise ValueError(f"Number of inputs can't exceed 4. {order = }.")
        try:
            creation_func = self.f_lookup[lookup][val_type]
        except KeyError:
            raise TypeError(f"Type {val_type} not valid for widget style {lookup}.")

        item_dict = {'tag' : name,
                     'default_value' : value,
                     'callback' : callback,
                     }
        if order > 1:
            item_dict['size'] = order
        item_dict.update(item_kwargs)
        with dpg.group(horizontal=True,parent=parent):
            dpg.add_text(f"{hierarchy[-1]}:",tag=f"{name}_label")
            creation_func(**item_dict)

    def save(self,filemode='w'):
        with dpg.mutex():
            path = Path(self.savefile)
            if not path.exists():
                path.touch()
            values_dict = self.collapse_item_dict(self.dict)
            with path.open(filemode) as f:
                for key,value in values_dict.items():
                    if key not in self.skip_save:
                        f.write(f"{key},{value}\n")
    
    def collapse_item_dict(self, d:dict):
        output = {}
        for key, item in d.items():
            if isinstance(item,dict):
                output.update(self.collapse_item_dict(item))
            elif isinstance(item,str):
                output.update({item : self[item]})
            else:
                ValueError(f"Invalid entry found in dict {item}. This shouldn't be possible.")
        return output

    def load(self):
        path = Path(self.savefile)
        if not path.exists():
            return
        with path.open('r') as f:
            for line in f.readlines():
                entries = line.split(',',maxsplit=1)
                entries = [entry.strip() for entry in entries]
                if entries[0] in self.skip_save:
                    continue
                try:
                    self.add(entries[0],literal_eval(entries[1]))
                except RuntimeError:
                    self[entries[0]] = literal_eval(entries[1])
                # If we can't evaluate it, just add it as a string.
                except ValueError:
                    try:
                        self.add(entries[0],entries[1])
                    except RuntimeError:
                        self[entries[0]] = entries[1]

    def get_save_callback(self):
        return lambda _: self.save()

def initialize_dpg(title:str = "Unamed DPG App"):
    dpg.create_context()
    dpg.configure_app(
        wait_for_input=False, # Can set to true but items may not live update. Lowers CPU usage
        )
    dpg.create_viewport(title=title, width=600, height=300)
    with dpg.font_registry():
        dpg.add_font("X:\DiamondCloud\Personal\Rigel\Scripts\FiraCode-Bold.ttf", 18, default_font=True)
        dpg.add_font("X:\DiamondCloud\Personal\Rigel\Scripts\FiraCode-Medium.ttf", 18, default_font=False)
        dpg.add_font("X:\DiamondCloud\Personal\Rigel\Scripts\FiraCode-Regular.ttf", 18, default_font=False)
        dpg.add_font("X:\DiamondCloud\Personal\Rigel\Scripts\FiraCode-Bold.ttf", 22, default_font=False, id="plot_font")

def start_dpg():
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.maximize_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()