@echo off
echo 正在安装依赖...
pip install -r requirements.txt
echo.
echo 启动 InsureMEP Dashboard...
streamlit run app.py
pause
