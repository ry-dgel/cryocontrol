from multiprocessing.sharedctypes import Value
import dearpygui.dearpygui as dpg
from dearpygui_ext.logger import mvLogger
from typing import Union, Any
from pathlib import Path
from ast import literal_eval
import itertools

class TreeDict():

    def __init__(self, parent:Union[str,int]) -> None:
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
        self.savefile = 'test_tree.csv'
        dpg.set_frame_callback(1,lambda _: self.load())


    def __getitem__(self, key):
        return dpg.get_value(key)

    def __setitem__(self,key,value):
        dpg.set_value(key,value)
    
    def add(self, name:str, value:Any, val_type:type = None, 
            order:int=1, drag:bool = False, callback = None,
            node_kwargs:dict = {}, item_kwargs:dict = {}):

        if callback is None:
            callback = self.get_save_callback()

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
        docking=True,
        docking_space=True
        )
    dpg.create_viewport(title=title, width=600, height=300)

def start_dpg():
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()

# The Actual App
initialize_dpg()

dpg.add_window(tag='main_window', label="Test Window")
tree = TreeDict(parent="main_window")
tree.add('First/test1', 0.1)
tree.add('First/test2', 1)
tree.add('Second/test1', 'abcd')
tree.add('Second/test2', True)
tree.add('Third/test1', [1,2,3,4])
tree.add('Third/test2', [0.1,0.2,0.3,0.4])
tree.add('Fourth/test1', 0.1, drag=True)
tree.add('Fourth/test2', 1, drag=True)
tree.add('Fourth/test3', [1,2,3,4], drag=True)
tree.add('Fourth/test4', [0.1,0.2,0.3,0.4], drag=True)
dpg.show_item_registry()

start_dpg()