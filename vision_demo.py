import gradio as gr
import json
from test_end_to_end import analyze_image_with_gemini

def process_upload(image_filepath):
    if not image_filepath:
        return "No image selected."
    try:
        res = analyze_image_with_gemini(image_filepath)
        return json.dumps(res, indent=4, ensure_ascii=False)
    except Exception as e:
        return f"Error analyzing image: {e}"

capstone_ui = gr.Interface(
    fn=process_upload,
    inputs=gr.Image(type="filepath", label="Upload Asset Photo (HVAC/Electrical/etc.)"),
    outputs=gr.Code(language="json", label="Agentic Grid Vision Analysis Result"),
    title="InsureMEP - Gemini Vision Onboarding Engine",
    description="Upload a photo of an industrial or mechanical asset. The AI will analyze the image to detect visual defects (leak/corrosion), identify the asset type, check safety valves, and output a structured JSON schema ready for the database.",
    theme="default"
)

if __name__ == "__main__":
    print("Launching Gradio UI for Vision Model...")
    capstone_ui.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True)
