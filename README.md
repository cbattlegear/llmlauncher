# LLM Launcher 🚀

LLM Launcher is a simple LLM testing tool allowing you to quickly test a single prompt across multiple models. 

You can use LLM Launcher right now @ https://llmlauncher.com or you can self host the application with docker by running: 

```
docker run -p 8501:8501 cbattlegear/llmlauncher
```

Either way you use it all of your data and settings are kept locally and only used to run the models. 

[Built on Streamlit](https://streamlit.io/)

## Contributing new models

Check out model_types/azure_openai.toml.example to see a working example with comments. Once you've created one feel free to send over a PR!