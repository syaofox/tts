# 来源 https://github.com/OS984/DiscordBotBackend/blob/3b06b8be39e4dbc07722b0afefeee4c18c136102/NeuralTTS.py
# A completely innocent attempt to borrow proprietary Microsoft technology for a much better TTS experience
import os
import subprocess
from unittest import result
import requests
import websockets
import asyncio
from datetime import datetime
import time
import re
import uuid
import fire
import argparse
'''命令行参数解析'''


def cut(obj, sec):
    return [obj[i:i + sec] for i in range(0, len(obj), sec)]


def parseArgs():
    parser = argparse.ArgumentParser(description='text2speech')
    parser.add_argument('--input', dest='input', help='SSML(语音合成标记语言)的路径', type=str, required=True)
    parser.add_argument('--output', dest='output', help='保存mp3文件的路径', type=str, required=False)
    args = parser.parse_args()
    return args


# Fix the time to match Americanisms
def hr_cr(hr):
    corrected = (hr - 1) % 24
    return str(corrected)


# Add zeros in the right places i.e 22:1:5 -> 22:01:05
def fr(input_string):
    corr = ''
    i = 2 - len(input_string)
    while (i > 0):
        corr += '0'
        i -= 1
    return corr + input_string


# Generate X-Timestamp all correctly formatted
def getXTime():
    now = datetime.now()
    return fr(str(now.year)) + '-' + fr(str(now.month)) + '-' + fr(str(now.day)) + 'T' + fr(hr_cr(int(now.hour))) + ':' + fr(str(now.minute)) + ':' + fr(str(now.second)) + '.' + str(now.microsecond)[:3] + 'Z'


# Async function for actually communicating with the websocket
async def transferMsTTSData(SSML_text, outputPath):
    # endpoint1 = "https://azure.microsoft.com/en-gb/services/cognitive-services/text-to-speech/"
    # r = requests.get(endpoint1)
    # main_web_content = r.text
    # # They hid the Auth key assignment for the websocket in the main body of the webpage....
    # token_expr = re.compile('token: \"(.*?)\"', re.DOTALL)
    # Auth_Token = re.findall(token_expr, main_web_content)[0]
    # req_id = str('%032x' % random.getrandbits(128)).upper()
    # req_id is generated by uuid.
    req_id = uuid.uuid4().hex.upper()
    print(req_id)
    # wss://eastus.api.speech.microsoft.com/cognitiveservices/websocket/v1?TrafficType=AzureDemo&Authorization=bearer%20undefined&X-ConnectionId=577D1E595EEB45979BA26C056A519073
    # endpoint2 = "wss://eastus.tts.speech.microsoft.com/cognitiveservices/websocket/v1?Authorization=" + \
    #     Auth_Token + "&X-ConnectionId=" + req_id
    # 目前该接口没有认证可能很快失效
    endpoint2 = f"wss://eastus.api.speech.microsoft.com/cognitiveservices/websocket/v1?TrafficType=AzureDemo&Authorization=bearer%20undefined&X-ConnectionId={req_id}"
    async with websockets.connect(endpoint2) as websocket:
        payload_1 = '{"context":{"system":{"name":"SpeechSDK","version":"1.12.1-rc.1","build":"JavaScript","lang":"JavaScript","os":{"platform":"Browser/Linux x86_64","name":"Mozilla/5.0 (X11; Linux x86_64; rv:78.0) Gecko/20100101 Firefox/78.0","version":"5.0 (X11)"}}}}'
        message_1 = 'Path : speech.config\r\nX-RequestId: ' + req_id + '\r\nX-Timestamp: ' + \
            getXTime() + '\r\nContent-Type: application/json\r\n\r\n' + payload_1
        await websocket.send(message_1)

        payload_2 = '{"synthesis":{"audio":{"metadataOptions":{"sentenceBoundaryEnabled":false,"wordBoundaryEnabled":false},"outputFormat":"audio-24khz-96kbitrate-mono-mp3"}}}'
        # payload_2 = '{"synthesis":{"audio":{"metadataOptions":{"sentenceBoundaryEnabled":false,"wordBoundaryEnabled":false},"outputFormat":"audio-16khz-32kbitrate-mono-mp3"}}}'

        message_2 = 'Path : synthesis.context\r\nX-RequestId: ' + req_id + '\r\nX-Timestamp: ' + \
            getXTime() + '\r\nContent-Type: application/json\r\n\r\n' + payload_2
        await websocket.send(message_2)

        # payload_3 = '<speak xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xmlns:emo="http://www.w3.org/2009/10/emotionml" version="1.0" xml:lang="en-US"><voice name="' + voice + '"><mstts:express-as style="General"><prosody rate="'+spd+'%" pitch="'+ptc+'%">'+ msg_content +'</prosody></mstts:express-as></voice></speak>'
        payload_3 = SSML_text
        message_3 = 'Path: ssml\r\nX-RequestId: ' + req_id + '\r\nX-Timestamp: ' + \
            getXTime() + '\r\nContent-Type: application/ssml+xml\r\n\r\n' + payload_3
        await websocket.send(message_3)

        # Checks for close connection message
        end_resp_pat = re.compile('Path:turn.end')
        audio_stream = b''
        while (True):
            response = await websocket.recv()
            print('receiving...')
            # Make sure the message isn't telling us to stop
            if (re.search(end_resp_pat, str(response)) == None):
                # Check if our response is text data or the audio bytes
                if type(response) == type(bytes()):
                    # Extract binary data
                    try:
                        needle = b'Path:audio\r\n'
                        start_ind = response.find(needle) + len(needle)
                        audio_stream += response[start_ind:]
                    except:
                        pass
            else:
                break
        with open(f'{outputPath}.mp3', 'wb') as audio_out:
            audio_out.write(audio_stream)


async def mainSeq(SSML_text, outputPath):
    await transferMsTTSData(SSML_text, outputPath)


def get_SSML(path):
    with open(path, 'r', encoding='utf-8') as f:
        head = '''
        <speak xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xmlns:emo="http://www.w3.org/2009/10/emotionml" version="1.0" xml:lang="en-US"><voice name="zh-CN-XiaochenNeural"><prosody rate="7%" pitch="0%">
        '''

        #         head = '''
        #         <!--ID=B7267351-473F-409D-9765-754A8EBCDE05;Version=1|{"VoiceNameToIdMapItems":[{"Id":"16cf511c-1865-404e-b2da-160362b7dff6","Name":"Microsoft Server Speech Text to Speech Voice (zh-CN, XiaochenNeural)","ShortName":"zh-CN-XiaochenNeural","Locale":"zh-CN","VoiceType":"StandardVoice"}]}-->
        # <!--ID=FCB40C2B-1F9F-4C26-B1A1-CF8E67BE07D1;Version=1|{"Files":{}}-->
        # <!--ID=5B95B1CC-2C7B-494F-B746-CF22A0E779B7;Version=1|{"Locales":{"zh-CN":{"AutoApplyCustomLexiconFiles":[{}]}}}-->
        # <speak xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xmlns:emo="http://www.w3.org/2009/10/emotionml" version="1.0" xml:lang="en-US"><voice name="zh-CN-XiaochenNeural"><prosody rate="+4%" pitch="+0%" volume="+20.00%">
        #         '''
        content = f.read()

        # content_list = cut(content, 10)
        # content_list = cut(content, 10)
        ## 去掉空行，按行分割

        # content_list = filter(None, content.split('\n'))

        result_list = []
        content_list = content.split('\n')

        line_result = ''
        idx = 0

        for line in content_list:
            idx += 1

            if line == '' or line is None:
                continue
            if line.startswith('－'):
                continue

            line_result = line_result + '\n' + line + '\n'

            if (len(line_result) + len(line) >= 800):
                result_list.append(f'{head}{line_result}</prosody></voice></speak>')
                line_result = ''

        result_list.append(f'{head}{line_result}</prosody></voice></speak>')
        return result_list


def run(input):
    SSML_text_list = get_SSML(input)
    print(os.path.dirname(input))
    data_dir = os.path.dirname(input)
    data_name = os.path.basename(input)
    datafile = os.path.join(data_dir, "data.txt")
    print(data_name)

    tempfiles = []
    tempfiles.append(datafile)

    with open(datafile, "a+") as f:
        for idx, SSML_text in enumerate(SSML_text_list):
            output_path = os.path.join(data_dir, f'{data_name}_{str(idx)}')

            tempfiles.append(f'{output_path}.mp3')
            if os.path.exists(output_path + '.mp3'):
                print(f'跳过{output_path}')
                continue
            f.write(f"file \'{output_path}.mp3\'\n")

            asyncio.get_event_loop().run_until_complete(mainSeq(SSML_text, output_path))
            time.sleep(10)

    outfile = output_path = os.path.join(data_dir, f'{data_name}')

    strcmd = f'ffmpeg -f concat -safe 0 -i "{datafile}" -c copy "{outfile}.mp3"'
    subprocess.run(strcmd, shell=True)

    for xfname in tempfiles:
        if os.path.exists(xfname):
            os.remove(xfname)

    print('completed')


if __name__ == "__main__":
    fire.Fire(run)
    # args = parseArgs()
    # SSML_text_list = get_SSML(args.input)
    # print(os.path.dirname(args.input))
    # data_dir = os.path.dirname(args.input)
    # data_name = os.path.basename(args.input)
    # datafile = os.path.join(data_dir, "data.txt")
    # print(data_name)

    # tempfiles = []
    # tempfiles.append(datafile)

    # with open(datafile, "w") as f:
    #     for idx, SSML_text in enumerate(SSML_text_list):
    #         output_path = os.path.join(data_dir, f'{data_name}_{str(idx)}')
    #         tempfiles.append(f'{output_path}.mp3')
    #         f.write(f"file \'{output_path}.mp3\'\n")

    #         asyncio.get_event_loop().run_until_complete(mainSeq(SSML_text, output_path))

    # outfile = output_path = os.path.join(data_dir, f'{data_name}')

    # strcmd = f'ffmpeg -f concat -safe 0 -i "{datafile}" -c copy "{outfile}.mp3"'
    # subprocess.run(strcmd, shell=True)

    # for xfname in tempfiles:
    #     if os.path.exists(xfname):
    #         os.remove(xfname)

    # print('completed')

    # SSML_text = get_SSML(args.input)
    # output_path = args.output if args.output else 'output_' + str(int(time.time() * 1000))
    # asyncio.get_event_loop().run_until_complete(mainSeq(SSML_text, output_path))
    # print('completed')
    # python tts.py --input SSML.xml
    # python tts.py --input SSML.xml --output 保存文件名