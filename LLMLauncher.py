import streamlit as st
from streamlit_local_storage import LocalStorage
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit import runtime

from string import Template
import requests
import toml
import json
from pathlib import Path
from jsonpath_ng import parse
from joblib import Parallel, delayed
import time
import os

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry import trace, metrics
from opentelemetry.propagate import extract
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

def LocalStorageManager():
    return LocalStorage()

@st.cache_resource()
def _configure_logging(APPLICATIONINSIGHTS_CONNECTION_STRING):
    os.environ["OTEL_SERVICE_NAME"] = "llm_launcher"
    print("Configuring logging")
    if APPLICATIONINSIGHTS_CONNECTION_STRING is not None:
        print("Configuring Azure Monitor")
        configure_azure_monitor()
    else:
        # Set up a tracer provider
        trace.set_tracer_provider(TracerProvider())

        # Configure the tracer to export spans to the console
        span_processor = BatchSpanProcessor(ConsoleSpanExporter())
        trace.get_tracer_provider().add_span_processor(span_processor)


        metrics.set_meter_provider(MeterProvider(metric_readers=[PeriodicExportingMetricReader(meter_exporter=ConsoleMetricExporter())]))
    
    tracer = trace.get_tracer(__name__)
    meter = metrics.get_meter(__name__)

    run_counter = meter.create_counter("run_count")

    return (tracer, run_counter)

@st.dialog("Add LLM")
def add_llm_dialog(llm_configs):
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
def edit_llm_dialog(llm_name, llm_configs):
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

def edit_llm(llm_name, llm_configs):
    if llm_name in st.session_state.llms["llm_objects"]:
        edit_llm_dialog(llm_name, llm_configs)

def run_llm(run_data, ctx):
    #tracer = trace.get_tracer(__name__)
    #context = TraceContextTextMapPropagator().extract(carrier=ctx)
    #with tracer.start_as_current_span(
    #    "run_llm_model",
    #    context=context):
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

def display_llm_results(llm_system_prompt, llm_user_prompt, llms, llm_configs, tracer):
    with st.spinner("Generating Responses..."):
        trace_context_carrier = {}
        TraceContextTextMapPropagator().inject(carrier=trace_context_carrier)
        ctx = TraceContextTextMapPropagator().extract(trace_context_carrier)
        with tracer.start_as_current_span(
        "generate_llm_responses",
        kind=trace.SpanKind.SERVER,
        context=ctx):
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

                llm_data = llms["llm_objects"][llm_key]
                llm_data["llm_system_prompt"] = llm_system_prompt
                llm_data["llm_user_prompt"] = llm_user_prompt

                url = endpoint_template.substitute(llm_data)

                headers_json = header_template.substitute(llm_data)
                headers = json.loads(headers_json)
                
                data_json = data_template.substitute(llm_data)
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

            output_gen = parallel(delayed(run_llm)(run_data, trace_context_carrier) for run_data in run_list)
            response_tabs = st.tabs(display_list)
        
        for output in output_gen:
            #runtime_string = output["run_time"].strftime("%S.%f").rstrip("0")
            with response_tabs[output["response_index"]]:
                st.write(output["llm_text"])
                with st.expander("Response Details"):
                    st.write(f"Runtime: {output['run_time']:.3f}s")
                    st.write(output["llm_details"])

        prompts = {
            "system_prompt": llm_system_prompt,
            "user_prompt": llm_user_prompt
        }

        st.session_state.run = False
        st.session_state.prompts = prompts
        localS = LocalStorageManager()
        localS.setItem("prompts", prompts, key="set_prompts_on_generate")

def get_client_ip():
    ip = None
    if "X_FORWARDED_FOR" in st.context.headers:
        ip = st.context.headers["X_FORWARDED_FOR"]
    elif "REMOTE_ADDR" in st.context.headers:
        ip = st.context.headers["REMOTE_ADDR"]
    else:
        ctx = get_script_run_ctx()
        if ctx is None:
            ip = None
        else: 
            session_info = runtime.get_instance().get_client(ctx.session_id)
            ip = session_info.request.remote_ip

    return ip

def main() -> None:
    st.set_page_config(page_title="LLM Launcher", page_icon="🚀", layout="wide")

    llm_configs = {}

    toml_directory = Path("model_types")
    for toml_file in toml_directory.glob("*.toml"):
        with open(toml_file, "r") as f:
            llm_config = toml.load(f)
            llm_configs[llm_config["information"]["model_name"]] = llm_config
    llm_configs = dict(sorted(llm_configs.items()))

    if "APPLICATIONINSIGHTS_CONNECTION_STRING" in os.environ:
        appinsights = os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
    else:
        appinsights = None
    tracer, run_counter = _configure_logging(appinsights)
    
    with tracer.start_as_current_span(
        "server_request",
        kind=trace.SpanKind.SERVER) as span:
        span.set_attribute("http.client_ip", get_client_ip())
        st.title("LLM Launcher")

        llms = {
            "llm_objects": {}
        }

        prompts = {
            "system_prompt": "",
            "user_prompt": ""
        }

        localS = LocalStorageManager()

        if "run" not in st.session_state:
            st.session_state.run = False

        if "llms" in st.session_state:
            llms = st.session_state.llms
        elif localS.getItem("llms") is not None:
            llms = localS.getItem("llms")
            st.session_state.llms = llms
        else:
            st.session_state.llms = llms

        if "prompts" in st.session_state:
            prompts = st.session_state.prompts
        elif localS.getItem("prompts") is not None:
            prompts = localS.getItem("prompts")
            st.session_state.prompts = prompts
        else:
            st.session_state.prompts = prompts

        with st.sidebar:
            st.header("LLM Launcher")
            st.write("A tool to launch multiple LLMs at once for testing and fun!")
            st.write("Make sure to add some LLMs, once you've done that we will save all configurations locally for you.")
            st.divider()
            st.write("Made with ❤️ by [Cameron Battagler](https://github.com/cbattlegear)")
            st.write("Contribute on [GitHub](https://github.com/cbattlegear/llmlauncher)")
            st.write(f"Version [{os.environ.get('LAUNCHER_VERSION', 'Development')}](https://github.com/cbattlegear/llmlauncher/releases/tag/{os.environ.get('LAUNCHER_VERSION', 'Development')})")

        with st.expander("Currently Configured LLMs"):
            column_list = []
            row_count = 0
            for llm_key, llm in llms["llm_objects"].items():
                column_list.append(st.columns((1, 0.5, 0.5)))
                with column_list[row_count][0]:
                    st.write(llm["llm_name"] + " (" + llm["llm_model"] + ")") 
                with column_list[row_count][1]:
                    st.button("Edit", key=llm_key + "edit", on_click=edit_llm, args=[llm_key, llm_configs], type="secondary", icon=":material/edit:")
                with column_list[row_count][2]:
                    st.button("Remove", key=llm_key + "delete", on_click=del_llm, args=[llm_key], type="primary", icon=":material/delete:")
                row_count += 1

        if st.button("Add LLM"):
            add_llm_dialog(llm_configs)

        if len(st.session_state.llms["llm_objects"]) > 0:
            llm_system_prompt = st.text_area("System Prompt", height=100, value=st.session_state.prompts["system_prompt"])
            llm_user_prompt = st.text_area("User Prompt", height=100, value=st.session_state.prompts["user_prompt"])

            col1, col2 = st.columns((1, 1))

            if col1.button("Generate Responses"):
                st.session_state.run = True
                st.rerun()

            if col2.button("Clear Responses and Prompts"):
                prompts = {
                    "system_prompt": None,
                    "user_prompt": None
                }
                st.session_state.prompts = prompts
                st.rerun()

            if st.session_state.run:
                run_counter.add(1, {"run": "generate_llm_responses"})
                display_llm_results(llm_system_prompt, llm_user_prompt, llms, llm_configs, tracer)
                for llm_key, llm in llms["llm_objects"].items():
                    run_counter.add(1, {"run": llm_key})
                

        if "llms" in st.session_state:
            localS.setItem("llms", llms)

        if "prompts" in st.session_state:
            localS.setItem("prompts", prompts, key="set_prompts")

main()