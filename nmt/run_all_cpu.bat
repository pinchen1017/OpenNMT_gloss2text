:: 1) 卸載 pip 與清快取
python -m pip uninstall -y torch torchvision torchaudio
python -m pip cache purge

:: 2) 嘗試移除 conda 版本（若沒 conda 也沒關係）
conda remove -n gloss2zh pytorch torchvision torchaudio -y

:: 3) 直接刪掉環境內的 torch 目錄
rmdir /s /q "%CONDA_PREFIX%\Lib\site-packages\torch"
rmdir /s /q "%CONDA_PREFIX%\Lib\site-packages\torchvision"
rmdir /s /q "%CONDA_PREFIX%\Lib\site-packages\torchaudio"

:: 4) 重新安裝 CPU 版（不走預設 PyPI）
python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch

:: 5) 驗證
python -c "import torch; print('ok', torch.__version__, 'cuda?', torch.cuda.is_available())"

:: 6) 再建 vocab
python -m onmt.bin.build_vocab -config .\onmt.tiny.cpu.yaml -n_sample -1
