import streamlit as st
from streamlit_local_storage import LocalStorage
from string import Template
import requests
import toml
import json
from pathlib import Path
from jsonpath_ng import parse
from joblib import Parallel, delayed
import time
import os

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

def run_llm(run_data):
    start_time = time.time()
    response = requests.post(run_data['url'], headers=run_data['headers'], json=run_data['data'])
    llm_response = {}
    llm_response["status_code"] = response.status_code
    llm_response["response_index"] = run_data["index"]

    if response.status_code == 200:
        path_expr = parse(run_data['json_path'])
        llm_response["llm_text"] = [match.value for match in path_expr.find(response.json())][0]
        llm_response["llm_details"] = response.json()
    else:
        llm_response["llm_text"] = "Request failed"
        llm_response["llm_details"] = response.text

    llm_response["run_time"] = (time.time() - start_time)

    return llm_response

with st.sidebar:
    st.header("LLM Launcher")
    st.write("A tool to launch multiple LLMs at once for testing and fun!")
    st.write("Make sure to add some LLMs, once you've done that we will save all configurations locally for you.")
    st.divider()
    st.write("Made with ❤️ by [Cameron Battagler](https://github.com/cbattlegear)")
    st.write("Contribute on [GitHub](https://github.com/cbattlegear/llmlauncher)")
    st.write(f"Version [{os.environ.get('LAUNCHER_VERSION', 'Development')}](https://github.com/cbattlegear/llmlauncher/releases/tag/{os.environ.get('LAUNCHER_VERSION', 'Development')})")

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
            item_index = 0
            run_list = []
            for llm_key, llm in llms["llm_objects"].items():
                display_list.append(llm['llm_name'] + " (" + llm['llm_model'] + ")")
                run_data = {}
                endpoint_template = Template(llm_configs[llm['llm_model']]["templates"]["endpoint_template"])
                header_template = Template(llm_configs[llm['llm_model']]["templates"]["header_template"])
                data_template = Template(llm_configs[llm['llm_model']]["templates"]["data_template"])
                
                for id in endpoint_template.get_identifiers():
                    llms["llm_objects"][llm_key][id] = llms["llm_objects"][llm_key][id].rstrip("/")

                url = endpoint_template.substitute(llms["llm_objects"][llm_key])

                headers_json = header_template.substitute(llms["llm_objects"][llm_key])
                headers = json.loads(headers_json)
                
                data_json = data_template.substitute(llm_system_prompt=llm_system_prompt, llm_user_prompt=llm_user_prompt)
                data = json.loads(data_json)

                run_data["url"] = url
                run_data["headers"] = headers
                run_data["data"] = data
                run_data["display_name"] = llm['llm_name'] + " (" + llm['llm_model'] + ")"
                run_data["index"] = item_index
                run_data["json_path"] = llm_configs[llm['llm_model']]["templates"]["response_path"]
                run_list.append(run_data)
                item_index += 1

            parallel = Parallel(n_jobs=6, return_as="list")

            output_gen = parallel(delayed(run_llm)(run_data) for run_data in run_list)
            response_tabs = st.tabs(display_list)
            
            for output in output_gen:
                #runtime_string = output["run_time"].strftime("%S.%f").rstrip("0")
                with response_tabs[output["response_index"]]:
                    st.write(output["llm_text"])
                    with st.expander("Response Details"):
                        st.write(f"Runtime: {output['run_time']:.3f}s")
                        st.write(output["llm_details"])

            localS.setItem("llm_system_prompt", llm_system_prompt, key="llm_system_prompt")
            localS.setItem("llm_user_prompt", llm_user_prompt, key="llm_user_prompt")