import streamlit as st
from streamlit_local_storage import LocalStorage
from string import Template
import requests
import toml
import json
from pathlib import Path
from jsonpath_ng import jsonpath, parse

st.title("LLM Launcher")

llms = {
    "llm_objects": {}
}

llm_configs = {}

localS = LocalStorage()

if "llms" in st.session_state:
    llms = st.session_state.llms
    localS.setItem("llms", llms)
elif localS.getItem("llms") is not None:
    llms = localS.getItem("llms")
    st.session_state.llms = llms
else:
    st.session_state.llms = llms

toml_directory = Path("model_types")
for toml_file in toml_directory.glob("*.toml"):
    with open(toml_file, "r") as f:
        llm_config = toml.load(f)
        llm_configs[llm_config["information"]["model_name"]] = llm_config

@st.dialog("Add LLM")
def add_llm_dialog():
    llm_model = st.selectbox("LLM Type", list(llm_configs.keys()))
    config_items = {}
    if llm_model is not None:
        config_items['llm_name'] = st.text_input("LLM Name")
        config_items['llm_model'] = llm_model
        for item in llm_configs[llm_model]["properties"]:
            config_items[item["name"]] = st.text_input(item["description"])
        
        if st.button("Add"):
            if config_items['llm_name'] not in st.session_state.llms["llm_objects"]:
                st.session_state.llms["llm_objects"][config_items['llm_name']] = config_items
                st.write("LLM Added")
                st.rerun()

@st.dialog("Edit LLM")
def edit_llm_dialog(llm_name):
    llm_model = st.session_state.llms["llm_objects"][llm_name]["llm_model"]
    config_items = {}
    if llm_model is not None:
        config_items['llm_name'] = llm_name
        config_items['llm_model'] = llm_model
        for item in llm_configs[llm_model]["properties"]:
            config_items[item["name"]] = st.text_input(item["description"], value=st.session_state.llms["llm_objects"][llm_name][item["name"]])
        
        if st.button("Save"):
            if config_items['llm_name'] in st.session_state.llms["llm_objects"]:
                st.session_state.llms["llm_objects"][config_items['llm_name']] = config_items
                st.write("LLM Saved")
                st.rerun()

def del_llm(llm_name):
    if llm_name in st.session_state.llms["llm_objects"]:
        del st.session_state.llms["llm_objects"][llm_name]

def edit_llm(llm_name):
    if llm_name in st.session_state.llms["llm_objects"]:
        edit_llm_dialog(llm_name)

st.write("Add an LLM model to begin")

with st.expander("Currently Configured LLMs"):
    col1, col2, col3 = st.columns((1, 1, 1))
    for llm_key, llm in llms["llm_objects"].items():
        with col1:
            st.write(llm["llm_name"] + " (" + llm["llm_model"] + ")") 
        with col2:
            st.button("Edit", key=llm_key + "edit", on_click=edit_llm, args=[llm_key], type="secondary", icon=":material/edit:")
        with col3:
            st.button("Remove", key=llm_key + "delete", on_click=del_llm, args=[llm_key], type="primary", icon=":material/delete:")

if st.button("Add LLM"):
    add_llm_dialog()

if len(st.session_state.llms["llm_objects"]) > 0:
    llm_system_prompt_local = None
    if localS.getItem("llm_system_prompt") is not None:
        llm_system_prompt_local = localS.getItem("llm_system_prompt")
    
    llm_user_prompt_local = None
    if localS.getItem("llm_user_prompt") is not None:
        llm_user_prompt_local = localS.getItem("llm_user_prompt")

    llm_system_prompt = st.text_area("System Prompt", height=100, value=llm_system_prompt_local)
    llm_user_prompt = st.text_area("User Prompt", height=100, value=llm_user_prompt_local)
    if st.button("Generate Responses"):
        with st.spinner("Generating Responses..."):
            display_list = []
            for llm_key, llm in llms["llm_objects"].items():
                display_list.append(llm['llm_name'] + " (" + llm['llm_model'] + ")")

            response_tabs = st.tabs(display_list)
            item_index = 0
            for llm_key, llm in llms["llm_objects"].items():
                endpoint_template = Template(llm_configs[llm['llm_model']]["templates"]["endpoint_template"])
                header_template = Template(llm_configs[llm['llm_model']]["templates"]["header_template"])
                data_template = Template(llm_configs[llm['llm_model']]["templates"]["data_template"])


                url = endpoint_template.substitute(llms["llm_objects"][llm_key])

                headers_json = header_template.substitute(llms["llm_objects"][llm_key])

                headers = json.loads(headers_json)
                
                data_json = data_template.substitute(llm_system_prompt=llm_system_prompt, llm_user_prompt=llm_user_prompt)
                data = json.loads(data_json)

                response = requests.post(url, headers=headers, json=data)
                with response_tabs[item_index]:
                    if response.status_code == 200:
                        path_expr = parse(llm_configs[llm['llm_model']]["templates"]["response_path"])
                        st.write([match.value for match in path_expr.find(response.json())][0])
                        with st.expander("Response Details"):
                            st.write(response.json())
                    else:
                        st.write("Request failed:", response.status_code, response.text)
                item_index += 1
            localS.setItem("llm_system_prompt", llm_system_prompt, key="llm_system_prompt")
            localS.setItem("llm_user_prompt", llm_user_prompt, key="llm_user_prompt")