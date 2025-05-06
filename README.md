# 1. 简介
使用micropython基于esp32c3开发版的一套驱动

* 输入：INMP441 I2S麦克风模块
* 输出：MAX98357 I2S音频放大器 + 3w8Ω扬声器
* oled显示：0.96寸(128x64)的I2C oled显示屏

# 2. 安装
## 1. 烧录esp32c3 micropython固件
使用[thonny](https://thonny.org/)完成烧录

## 2. 上传本仓库驱动
使用vscode + pymakr完成

# 3. 功能描述
1. 按esp32c3开发板上的'BOOT'键开启语音输入模式
2. oled显示屏会实时显示当前状态
3. 发送语音输入到后台[asr-llm-tts](https://github.com/esp32-qwen-ai/asr-llm-tts)中枢处理
4. 接收处理后的音频通过扬声器播放结果

# 4. 适配
修改`main.py`里的`Connection.HOST`和`Connection.PORT`为`asr-llm-tts`监听地址
