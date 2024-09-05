import requests
from bs4 import BeautifulSoup
import urllib3
import concurrent.futures
import pandas as pd  # 用于处理Excel输出
import chardet  # 用于检测网页的编码
from urllib.parse import urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class WebpackFind:
    def __init__(self):
        # 最大线程数（线程太高会出现多次停止进程，才能停止的情况，请根据自己的实际情况修改线程）
        self.max_workers = 30
        # Webpack的HTML指纹
        self.fingerprint_html = ['<noscript', 'webpackJsonp', '__webpack_require__', 'webpack-',
                                 '<script id=\"__NEXT_DATA__', '<style id=\"gatsby-inlined-css',
                                 '<div id=\"___gatsby', 'chunk', 'runtime', 'app.bundle', 'manifest']
        # Webpack的JavaScript指纹
        self.fingerprint_js = ['webpackJsonp', '__webpack_require__', 'webpackChunk']

        # 保存符合webpack特征的网址结果
        self.results = []

        # 使用 requests.Session() 复用连接，提升性能
        self.session = requests.Session()
        self.send_http_threads()

    def send_http_threads(self):
        urls = []
        with open('targets.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for url in lines:
                urls.append(url.strip())

        # 使用 ThreadPoolExecutor 并发请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {executor.submit(self.check_webpack, url): url for url in urls}

            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    future.result()  # 获取结果，检查是否有异常
                except Exception as e:
                    print(f"{url} 请求出错: {e}")

        # 在所有线程结束后，将结果写入Excel
        self.save_to_excel()

    def check_webpack(self, url):
        try:
            # 使用 session 发送 GET 请求，超时时间设置为 5 秒
            response = self.session.get(url, verify=False, timeout=5)

            # 使用 chardet 检测网页编码
            encoding = chardet.detect(response.content)['encoding']
            if encoding:
                response.encoding = encoding
            else:
                response.encoding = response.apparent_encoding

            content_length = len(response.content)  # 网页内容长度
            title = self.get_title(response.text)

            # 统计JS文件的数量
            js_num = self.count_js_files(response.text)

            # 检查 HTML 中的 Webpack 指纹
            if self.check_html_fingerprint(response.text):
                print(f"{url} 是 webpack（通过 HTML 指纹）")
                self.results.append({"URL": url, "Content Length": content_length, "Title": title, "JSNum": js_num})
            else:
                # 进一步检查 JavaScript 文件中的指纹
                if self.check_js_fingerprint(response, url):
                    print(f"{url} 是 webpack（通过 JS 文件指纹）")
                    self.results.append({"URL": url, "Content Length": content_length, "Title": title, "JSNum": js_num})

        except requests.exceptions.RequestException as e:
            print(f"请求 {url} 出现异常: {e}")

    def check_html_fingerprint(self, html):
        """
        检查网页 HTML 内容中是否包含 Webpack 的特征
        """
        return any(fingerprint in html for fingerprint in self.fingerprint_html)

    def check_js_fingerprint(self, response, base_url):
        """
        检查网页中引用的 JavaScript 文件，检测是否包含 Webpack 的特征
        """
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tags = soup.find_all('script')
        for script in script_tags:
            js_src = script.get('src')
            if js_src:
                # 完整的 JS 文件 URL
                js_url = urljoin(base_url, js_src)
                try:
                    # 请求 JavaScript 文件
                    js_response = self.session.get(js_url, verify=False, timeout=5)
                    js_response.encoding = chardet.detect(js_response.content)['encoding'] or 'utf-8'

                    # 检查 JS 文件中的 Webpack 指纹
                    if any(fingerprint in js_response.text for fingerprint in self.fingerprint_js):
                        return True
                except requests.exceptions.RequestException:
                    continue
        return False

    def count_js_files(self, html):
        """
        统计网页中 <script> 标签中引用的 JavaScript 文件数量
        """
        soup = BeautifulSoup(html, 'html.parser')
        script_tags = soup.find_all('script')
        js_num = sum(1 for script in script_tags if script.get('src'))  # 统计包含 src 属性的 <script> 标签数量
        return js_num

    def get_title(self, html):
        # 使用 BeautifulSoup 提取网页的标题
        soup = BeautifulSoup(html, 'html.parser')
        title_tag = soup.find('title')
        return title_tag.text.strip() if title_tag else "No Title"

    def save_to_excel(self):
        # 如果没有符合 webpack 的结果，则不生成 Excel 文件
        if self.results:
            # 使用 pandas 将结果保存为 Excel 文件
            df = pd.DataFrame(self.results)
            df.to_excel('results1.xlsx', index=False)
            print("结果已保存到 results1.xlsx")
        else:
            print("没有符合 webpack 的网址。")


if __name__ == '__main__':
    WebpackFind()
