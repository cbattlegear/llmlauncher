# LLM Launcher 🚀

LLM Launcher is a simple LLM testing tool [built on Streamlit](https://streamlit.io/), allowing you to quickly test a single prompt across multiple models. All of your data and settings are stored within your browser/client and is never sent to the servers behind LLMLauncher. In fact its just a basic front end webapp sending the API request to various LLM's directly through the browser session.

You can use LLM Launcher right now @ https://llmlauncher.com or you can self host the application with docker by running: 

```
docker run -p 8501:8501 cbattlegear/llmlauncher
```

### Usage

To get started, you will want the details of the LLM you are interacting with.

- Select Add LLM
  - LLM Type: Location of the LLM/Deployment type, e.g. deployed in Azure Open AI environment.
  - LLM Name: Name for your own identification purposes
  - LLM Endpoint URL: URL of LLM endpoint deployed, varies by location.
  - Deplomeny Name: Not all LLM Type's support this, mainly Azure deployed models environments.
  - API Key: API Key provided by LLM API provider.
  - Add!
- Once added, you can provide system and user prompts that will be ran against any LLM configurations you have added.
- Hit Generate Responses and watch the magic of hitting all configured LLM's with the provided prompts to see both their completion response as well as further metrics such as response time and token usage.
- Select "Currently Configured LLM's" to list all configured LLM's to edit or remove.

## Contributing new models

Check out [model_types/azure_openai.toml.example](model_types/azure_openai.toml.example) to see a working example with comments. Once you've created one feel free to send over a PR!
