// ==UserScript==
// @name         douyin-user-data-download
// @namespace    http://tampermonkey.net/
// @version      0.4.8
// @description  下载抖音用户主页数据!
// @author       xxmdmst
// @match        https://www.douyin.com/*
// @icon         https://xxmdmst.oss-cn-beijing.aliyuncs.com/imgs/favicon.ico
// @grant        GM_registerMenuCommand
// @grant        GM_setValue
// @grant        GM_getValue
// @require      https://cdnjs.cloudflare.com/ajax/libs/jszip/3.6.0/jszip.min.js
// @license MIT
// @downloadURL https://update.greasyfork.org/scripts/471880/douyin-user-data-download.user.js
// @updateURL https://update.greasyfork.org/scripts/471880/douyin-user-data-download.meta.js
// ==/UserScript==

(function () {
    let localDownload;
    let localDownloadUrl = GM_getValue("localDownloadUrl", 'http://localhost:8080/data');
    const startPipeline = (start) => {
        if (confirm(start ? "是否开启本地下载通道?\n开启后会向本地服务发送数据，服务地址：\n" + localDownloadUrl : "是否关闭本地下载通道?")) {
            GM_setValue("localDownload", start);
            window.location.reload();
        }
    }
    localDownload = GM_getValue("localDownload", false);
    if (localDownload) {
        GM_registerMenuCommand("✅关闭上报本地通道", () => {
            startPipeline(false);
        })
    } else {
        GM_registerMenuCommand("⛔️开启上报本地通道", () => {
            startPipeline(true);
        })
    }

    GM_registerMenuCommand("♐设置本地上报地址", () => {
        localDownloadUrl = GM_getValue("localDownloadUrl", 'http://localhost:8080/data');
        let newlocalDownloadUrl = prompt("请输入新的上报地址：", localDownloadUrl);
        if (newlocalDownloadUrl === null) {
            return;
        } else if (!newlocalDownloadUrl.trim()) {
            newlocalDownloadUrl = "http://localhost:8080/data";
            alert("设置了空白地址，已经恢复默认地址为:" + newlocalDownloadUrl);
            localDownloadUrl = newlocalDownloadUrl;
        } else {
            GM_setValue("localDownloadUrl", newlocalDownloadUrl);
            alert("当前上报地址已经修改为:" + newlocalDownloadUrl);
        }
        GM_setValue("localDownloadUrl", newlocalDownloadUrl);
        localDownloadUrl = newlocalDownloadUrl;
    });
    GM_registerMenuCommand("清空信息内容", () => msg_pre.textContent = "")
    let table;

    function initGbkTable() {
        // https://en.wikipedia.org/wiki/GBK_(character_encoding)#Encoding
        const ranges = [
            [0xA1, 0xA9, 0xA1, 0xFE],
            [0xB0, 0xF7, 0xA1, 0xFE],
            [0x81, 0xA0, 0x40, 0xFE],
            [0xAA, 0xFE, 0x40, 0xA0],
            [0xA8, 0xA9, 0x40, 0xA0],
            [0xAA, 0xAF, 0xA1, 0xFE],
            [0xF8, 0xFE, 0xA1, 0xFE],
            [0xA1, 0xA7, 0x40, 0xA0],
        ];
        const codes = new Uint16Array(23940);
        let i = 0;

        for (const [b1Begin, b1End, b2Begin, b2End] of ranges) {
            for (let b2 = b2Begin; b2 <= b2End; b2++) {
                if (b2 !== 0x7F) {
                    for (let b1 = b1Begin; b1 <= b1End; b1++) {
                        codes[i++] = b2 << 8 | b1
                    }
                }
            }
        }
        table = new Uint16Array(65536);
        table.fill(0xFFFF);
        const str = new TextDecoder('gbk').decode(codes);
        for (let i = 0; i < str.length; i++) {
            table[str.charCodeAt(i)] = codes[i]
        }
    }

    function str2gbk(str, opt = {}) {
        if (!table) {
            initGbkTable()
        }
        const NodeJsBufAlloc = typeof Buffer === 'function' && Buffer.allocUnsafe;
        const defaultOnAlloc = NodeJsBufAlloc
            ? (len) => NodeJsBufAlloc(len)
            : (len) => new Uint8Array(len);
        const defaultOnError = () => 63;
        const onAlloc = opt.onAlloc || defaultOnAlloc;
        const onError = opt.onError || defaultOnError;

        const buf = onAlloc(str.length * 2);
        let n = 0;

        for (let i = 0; i < str.length; i++) {
            const code = str.charCodeAt(i);
            if (code < 0x80) {
                buf[n++] = code;
                continue
            }
            const gbk = table[code];

            if (gbk !== 0xFFFF) {
                buf[n++] = gbk;
                buf[n++] = gbk >> 8
            } else if (code === 8364) {
                buf[n++] = 0x80
            } else {
                const ret = onError(i, str);
                if (ret === -1) {
                    break
                }
                if (ret > 0xFF) {
                    buf[n++] = ret;
                    buf[n++] = ret >> 8
                } else {
                    buf[n++] = ret
                }
            }
        }
        return buf.subarray(0, n)
    }

    function formatSeconds(seconds) {
        const timeUnits = ['小时', '分', '秒'];
        const timeValues = [
            Math.floor(seconds / 3600),
            Math.floor((seconds % 3600) / 60),
            seconds % 60
        ];
        return timeValues.map((value, index) => value > 0 ? value + timeUnits[index] : '').join('');
    }

    const timeFormat = (timestamp = null, fmt = 'yyyy-mm-dd') => {
        // 其他更多是格式化有如下:
        // yyyy:mm:dd|yyyy:mm|yyyy年mm月dd日|yyyy年mm月dd日 hh时MM分等,可自定义组合
        timestamp = parseInt(timestamp);
        // 如果为null,则格式化当前时间
        if (!timestamp) timestamp = Number(new Date());
        // 判断用户输入的时间戳是秒还是毫秒,一般前端js获取的时间戳是毫秒(13位),后端传过来的为秒(10位)
        if (timestamp.toString().length === 10) timestamp *= 1000;
        let date = new Date(timestamp);
        let ret;
        let opt = {
            "y{4,}": date.getFullYear().toString(), // 年
            "y+": date.getFullYear().toString().slice(2,), // 年
            "m+": (date.getMonth() + 1).toString(), // 月
            "d+": date.getDate().toString(), // 日
            "h+": date.getHours().toString(), // 时
            "M+": date.getMinutes().toString(), // 分
            "s+": date.getSeconds().toString() // 秒
            // 有其他格式化字符需求可以继续添加，必须转化成字符串
        };
        for (let k in opt) {
            ret = new RegExp("(" + k + ")").exec(fmt);
            if (ret) {
                fmt = fmt.replace(ret[1], (ret[1].length === 1) ? (opt[k]) : (opt[k].padStart(ret[1].length, "0")))
            }
        }
        return fmt
    };
    let user_aweme_list = [];
    let sec_uid = '';
    window.all_aweme_map = new Map();
    let userKey = [
        "昵称", "关注", "粉丝", "获赞",
        "抖音号", "IP属地", "性别",
        "位置", "签名", "作品数", "主页"
    ];
    let userData = [];
    let createEachButtonTimer;

    function copyText(text, node) {
        let oldText = node.textContent;
        navigator.clipboard.writeText(text).then(r => {
            node.textContent = "复制成功";
        }).catch((e) => {
            node.textContent = "复制失败";
        })
        setTimeout(() => node.textContent = oldText, 2000);
    }

    function copyUserData(node) {
        if (userData.length === 0) {
            alert("没有捕获到用户数据！");
            return;
        }
        let text = [];
        for (let i = 0; i < userKey.length; i++) {
            let key = userKey[i];
            let value = userData[userData.length - 1][i];
            if (value) text.push(key + "：" + value.toString().trim());
        }
        copyText(text.join("\n"), node);
    }

    function createVideoButton(text, top, func) {
        const button = document.createElement("button");
        button.textContent = text;
        button.style.position = "absolute";
        button.style.right = "0px";
        button.style.top = top;
        button.style.opacity = "0.5";
        if (func) {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                func();
            });
        }
        return button;
    }

    function createDownloadLink(blob, filename, ext, prefix = "") {
        if (filename === null) {
            filename = userData.length > 0 ? userData[userData.length - 1][0] : document.title;
        }
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = prefix + filename.replace(/[\/:*?"<>|\s]/g, "").slice(0, 40) + "." + ext;
        link.click();
        URL.revokeObjectURL(url);
    }

    function txt2file(txt, filename, ext) {
        createDownloadLink(new Blob([txt], {type: 'text/plain'}), filename, ext);
    }

    function getAwemeName(aweme) {
        let name = aweme.item_title ? aweme.item_title : aweme.caption;
        if (!name) name = aweme.desc ? aweme.desc : aweme.awemeId;
        return `【${aweme.date.slice(0, 10)}】` + name.replace(/[\/:*?"<>|\s]+/g, "").slice(0, 27).replace(/\.\d+$/g, "");
    }

    function createEachButton() {
        let targetNodes = document.querySelectorAll("div[data-e2e='user-post-list'] > ul[data-e2e='scroll-list'] > li a");
        for (let i = 0; i < targetNodes.length; i++) {
            let targetNode = targetNodes[i];
            if (targetNode.dataset.added) {
                continue;
            }
            let aweme = user_aweme_list[i];
            let copyDescButton = createVideoButton("复制描述", "0px");
            copyDescButton.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                copyText(aweme.desc, copyDescButton);
            })
            targetNode.appendChild(copyDescButton);
            targetNode.appendChild(createVideoButton("打开视频源", "20px", () => window.open(aweme.url)));
            const d = new Date(aweme.date);
            let filename = d.getFullYear() + "" + String(d.getMonth() + 1).padStart(2,'0') + ""
            + String(d.getDay() + 1).padStart(2,'0')+ "" + String(d.getHours()+1).padStart(2,'0')
            + String(d.getMinutes()+1).padStart(2,'0') + String(d.getSeconds()+1).padStart(2,'0')+'@'+aweme.awemeId;
            let downloadVideoButton = createVideoButton("下载视频", "40px", () => {
                let xhr = new XMLHttpRequest();
                xhr.open('GET', aweme.url.replace("http://", "https://"), true);
                xhr.responseType = 'blob';
                xhr.onload = (e) => {
                    createDownloadLink(xhr.response, filename, (aweme.images ? "mp3" : "mp4"));
                };
                xhr.onprogress = (event) => {
                    if (event.lengthComputable) {
                        downloadVideoButton.textContent = "下载" + (event.loaded * 100 / event.total).toFixed(1) + '%';
                    }
                };
                xhr.send();
            });
            targetNode.appendChild(downloadVideoButton);
            if (aweme.images) {
                let downloadImageButton = createVideoButton("图片打包下载", "60px", () => {
                    const zip = new JSZip();
                    downloadImageButton.textContent = "图片下载并打包中...";
                    const promises = aweme.images.map((link, index) => {
                        return fetch(link)
                            .then((response) => response.arrayBuffer())
                            .then((buffer) => {
                                downloadImageButton.textContent = `图片已下载【${index + 1}/${aweme.images.length}】`;
                                zip.file(`${index + 1}.jpg`, buffer);
                            });
                    });
                    const d = new Date(aweme.date);
                    let filename = d.getFullYear() + "" + String(d.getMonth() + 1).padStart(2,'0') + ""
                    + String(d.getDay() + 1).padStart(2,'0')+ "" + String(d.getHours()+1).padStart(2,'0')
                    + String(d.getMinutes()+1).padStart(2,'0') + String(d.getSeconds()+1).padStart(2,'0')+'@'+aweme.awemeId;
                    Promise.all(promises)
                        .then(() => {
                            return zip.generateAsync({type: "blob"});
                        })
                        .then((content) => {
                            createDownloadLink(content, filename, "zip");
                            downloadImageButton.textContent = "图文打包完成";
                        });
                });
                targetNode.appendChild(downloadImageButton);
            }
            targetNode.dataset.added = "true";
        }
    }

    function flush() {
        if (createEachButtonTimer !== undefined) {
            clearTimeout(createEachButtonTimer);
            createEachButtonTimer = undefined;
        }
        createEachButtonTimer = setTimeout(createEachButton, 500);
        data_button.p2.textContent = `${user_aweme_list.length}`;
        let img_num = user_aweme_list.filter(a => a.images).length;
        img_button.p2.textContent = `${img_num}`;
        msg_pre.textContent = `已加载${user_aweme_list.length}个作品，${img_num}个图文\n激活上方头像可展开下载按钮`;
    }

    let flag = false;

    const formatDouyinAwemeData = item => Object.assign(
        {
            "awemeId": item.aweme_id,
            "item_title": item.item_title,
            "caption": item.caption,
            "desc": item.desc,
            "tag": item.text_extra ? item.text_extra.map(tag => tag.hashtag_name).filter(tag => tag).join("#") : "",
            "video_tag": item.video_tag ? item.video_tag.map(tag => tag.tag_name).filter(tag => tag).join("->") : ""
        },
        item.statistics ? {
            "diggCount": item.statistics.digg_count,
            "commentCount": item.statistics.comment_count,
            "collectCount": item.statistics.collect_count,
            "shareCount": item.statistics.share_count
        } : {},
        item.video ? {
            "duration": formatSeconds(Math.round(item.video.duration / 1000)),
            "url": item.video.play_addr.url_list[0],
            "cover": item.video.cover.url_list[0],
            "images": item.images ? item.images.map(row => row.url_list.pop()) : null,
        } : {},
        {
            "date": timeFormat(item.create_time, "yyyy-mm-dd hh:MM:ss"),
            "uid": item.author.uid,
            "nickname": item.author.nickname
        }
    );


    function formatJsonData(json_data) {
        return json_data.aweme_list.map(formatDouyinAwemeData);
    }

    function sendLocalData(jsonData) {
        if (!localDownload) return;
        fetch(localDownloadUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(jsonData)
        })
            .then(response => response.json())
            .then(responseData => {
                console.log('成功:', responseData);
            })
            .catch(error => {
                console.log('上报失败，请检查本地程序是否已经启动！');
            });
    }

    function interceptResponse() {
        const originalSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send = function () {
            originalSend.apply(this, arguments);
            if (!this._url) return;
            this.url = this._url;
            if (this.url.startsWith("http"))
                this.url = new URL(this.url).pathname
            const self = this;
            let func = this.onreadystatechange;
            this.onreadystatechange = (e) => {
                if (self.readyState === 4) {
                    if (!self.url.startsWith("/aweme/v1/web/")) return;
                    let data = JSON.parse(self.response);
                    if (self.url.startsWith("/aweme/v1/web/aweme/post")) {
                        let jsonData = formatJsonData(data);
                        user_aweme_list.push(...jsonData);
                        if (domLoadedTimer === null) {
                            flush();
                        } else {
                            flag = true;
                        }
                    } else if (self.url.startsWith("/aweme/v1/web/user/profile/other")) {
                        let userInfo = data.user;
                        for (let key in userInfo) {
                            if (!userInfo[key]) userInfo[key] = "";
                        }
                        if (userInfo.district) userInfo.city += "·" + userInfo.district;
                        userInfo.unique_id = '\t' + (userInfo.unique_id ? userInfo.unique_id : userInfo.short_id);
                        sec_uid = userInfo.sec_uid
                        userData.push([
                            userInfo.nickname, userInfo.following_count, userInfo.mplatform_followers_count,
                            userInfo.total_favorited, userInfo.unique_id, userInfo.ip_location.replace("IP属地：", ""),
                            userInfo.gender === 2 ? "女" : "男",
                            userInfo.city, '"' + userInfo.signature + '"', userInfo.aweme_count, "https://www.douyin.com/user/" + userInfo.sec_uid
                        ]);
                    }
                    let jsonData;
                    if ([
                        "/aweme/v1/web/aweme/post/",
                        "/aweme/v1/web/aweme/related/",
                        "/aweme/v1/web/aweme/favorite/",
                        "/aweme/v1/web/tab/feed/",
                        "/aweme/v1/web/aweme/listcollection/",
                        "/aweme/v1/web/history/read/"
                    ].some(prefix => self.url.startsWith(prefix))) {
                        jsonData = formatJsonData(data);
                    } else if ([
                        "/aweme/v1/web/follow/feed/",
                        "/aweme/v1/web/familiar/feed/",
                    ].some(prefix => self.url.startsWith(prefix))) {
                        jsonData = data.data.filter(item => item.aweme).map(item => formatDouyinAwemeData(item.aweme));
                    } else if (self.url.startsWith("/aweme/v1/web/general/search/single/")) {
                        jsonData = [];
                        for (let obj of data.data) {
                            if (obj.aweme_info) jsonData.push(formatDouyinAwemeData(obj.aweme_info))
                            if (obj.user_list) {
                                for (let user of obj.user_list) {
                                    user.items.forEach(aweme => jsonData.push(formatDouyinAwemeData(aweme)))
                                }
                            }
                        }
                    } else if (self.url.startsWith("/aweme/v1/web/module/feed/")) {
                        jsonData = data.cards.map(item => formatDouyinAwemeData(JSON.parse(item.aweme)));
                    } else if (self.url.startsWith("/aweme/v1/web/aweme/detail/")) {
                        jsonData = [formatDouyinAwemeData(data.aweme_detail)]
                    }
                    if (jsonData) jsonData = jsonData.filter(item => item.url && item.awemeId);
                    if (jsonData) {
                        console.log(self.url, jsonData);
                        sendLocalData(jsonData);
                        jsonData.forEach(aweme => {
                            all_aweme_map.set(aweme.awemeId, aweme);
                        })

                    }
                }
                if (func) func.apply(self, e);
            };
        };
    }

    function downloadData(node, encoding) {
        if (user_aweme_list.length === 0) {
            alert("还没有发现作品数据，请进入https://www.douyin.com/user/开头的链接刷新网页后重试！");
            return;
        }
        if (node.disabled) {
            alert("下载正在处理中，请不要重复点击按钮！");
            return;
        }
        node.disabled = true;
        try {
            // if (userData.length > 0) {
            //     text += userKey.join(",") + "\n";
            //     text += userData.map(row => row.join(",")).join("\n") + "\n\n";
            // }
            let text = "作品描述,作品链接,作品id,发布时间,时长,标签,分类,封面,aweme_type,序号,下载链接,sec_uid,uid,nickname\n";
/*             user_aweme_list.forEach(aweme => {
                text += ['"' + aweme.desc.replace(/,/g, '，').replace(/"/g, '""') + '"',
                    "https://www.douyin.com/video/" + aweme.awemeId,aweme.awemeId.toString(),
                    aweme.date,aweme.duration, aweme.tag, aweme.video_tag,
                    aweme.cover, aweme.url,sec_uid].join(",") + "\n"
            }); */
            for (let i = 0; i <user_aweme_list.length; i++) {
                let imgs = user_aweme_list[i].images
                if(!imgs){
                    text += ['"' + user_aweme_list[i].desc.replace(/,/g, '，').replace(/"/g, '""') + '"',
                    "https://www.douyin.com/video/" + user_aweme_list[i].awemeId,user_aweme_list[i].awemeId+'',
                    user_aweme_list[i].date,user_aweme_list[i].duration, user_aweme_list[i].tag, user_aweme_list[i].video_tag,
                    user_aweme_list[i].cover,'video','',user_aweme_list[i].url,sec_uid,user_aweme_list[i].uid,user_aweme_list[i].nickname].join(",") + "\n"
                }else{
                    for (let j = 0; j <imgs.length; j++) {
                       text += ['"' + user_aweme_list[i].desc.replace(/,/g, '，').replace(/"/g, '""') + '"',
                        "https://www.douyin.com/video/" + user_aweme_list[i].awemeId,
                        user_aweme_list[i].awemeId, user_aweme_list[i].date,
                        user_aweme_list[i].duration, user_aweme_list[i].tag, user_aweme_list[i].video_tag,
                        user_aweme_list[i].cover,'image',j+1, user_aweme_list[i].images[j],sec_uid,user_aweme_list[i].uid,user_aweme_list[i].nickname].join(",") + "\n"
                    }
                }

            }
            if (encoding === "gbk") {
                text = str2gbk(text);
            }
            txt2file(text, null, "csv");
        } finally {
            node.disabled = false;
        }
    }

    let img_button, data_button, msg_pre;

    function createMsgBox() {
        msg_pre = document.createElement('pre');
        msg_pre.textContent = '等待上方头像加载完毕';
        msg_pre.style.color = 'white';
        msg_pre.style.position = 'fixed';
        msg_pre.style.right = '5px';
        msg_pre.style.top = '60px';
        msg_pre.style.color = 'white';
        msg_pre.style.zIndex = '90000';
        msg_pre.style.opacity = "0.5";
        document.body.appendChild(msg_pre);
    }

    function scrollPageToBottom(scroll_button) {
        let scrollInterval;

        function scrollLoop() {
            let endText = document.querySelector("div[data-e2e='user-post-list'] > ul[data-e2e='scroll-list'] + div div").innerText;
            if (endText || (userData.length > 0 && user_aweme_list.length > userData[userData.length - 1][9] - 5)) {
                clearInterval(scrollInterval);
                scrollInterval = null;
                scroll_button.p1.textContent = "已加载全部！";
            } else {
                scrollTo(0, document.body.scrollHeight);
            }
        }

        scroll_button.addEventListener('click', () => {
            if (!scrollInterval) {
                scrollInterval = setInterval(scrollLoop, 1200);
                scroll_button.p1.textContent = "停止自动下拉";
            } else {
                clearInterval(scrollInterval);
                scrollInterval = null;
                scroll_button.p1.textContent = "开启自动下拉";
            }
        });
    }

    function createCommonElement(tagName, attrs = {}, text = "") {
        const tag = document.createElement(tagName);
        for (const [k, v] of Object.entries(attrs)) {
            tag.setAttribute(k, v);
        }
        if (text) tag.textContent = text;
        tag.addEventListener('click', (event) => event.stopPropagation());
        return tag;
    }

    function createAllButton() {
        let dom = document.querySelector("#douyin-header-menuCt pace-island > div > div:nth-last-child(1) ul a:nth-last-child(1)");
        let baseNode = dom.cloneNode(true);
        baseNode.removeAttribute("target");
        baseNode.removeAttribute("rel");
        baseNode.removeAttribute("href");
        let svgChild = baseNode.querySelector("svg");
        if (svgChild) baseNode.removeChild(svgChild);

        function createNewButton(name, num = "0") {
            let button = baseNode.cloneNode(true);
            button.p1 = button.querySelector("p:nth-child(1)");
            button.p2 = button.querySelector("p:nth-child(2)");
            button.p1.textContent = name;
            button.p2.textContent = num;
            dom.after(button);
            return button;
        }

        img_button = createNewButton("图文打包下载");
        img_button.addEventListener('click', () => downloadImg(img_button));

        let downloadCoverButton = createNewButton("封面打包下载", "");
        downloadCoverButton.addEventListener('click', () => downloadCover(downloadCoverButton));

        data_button = createNewButton("下载已加载的数据");
        data_button.p1.after(createCommonElement("label", {'for': 'gbk'}, 'gbk'));
        let checkbox = createCommonElement("input", {'type': 'checkbox', 'id': 'gbk'});
        checkbox.checked = localStorage.getItem("gbk") === "1";
        checkbox.onclick = (event) => {
            event.stopPropagation();
            localStorage.setItem("gbk", checkbox.checked ? "1" : "0");
        };
        data_button.p1.after(checkbox);
        data_button.addEventListener('click', () => downloadData(data_button, checkbox.checked ? "gbk" : "utf-8"));

        scrollPageToBottom(createNewButton("开启自动下拉到底", ""));

        let share_button = document.querySelector("#frame-user-info-share-button");
        if (share_button) {
            let node = share_button.cloneNode(true);
            node.span = node.querySelector("span");
            node.span.innerHTML = "复制作者信息";
            node.addEventListener('click', () => copyUserData(node.span));
            share_button.after(node);
        }
    }

    async function downloadCover(node) {
        if (user_aweme_list.length === 0) {
            alert("还没有发现任何作品数据，请进入https://www.douyin.com/user/开头的链接刷新网页后重试！");
            return;
        }
        if (node.disabled) {
            alert("下载正在处理中，请不要重复点击按钮！");
            return;
        }
        node.disabled = true;
        try {
            const zip = new JSZip();
            msg_pre.textContent = `下载封面并打包中...`;
            let promises = user_aweme_list.map((aweme, index) => {
                let awemeName = getAwemeName(aweme) + ".jpg";
                return fetch(aweme.cover)
                    .then(response => response.arrayBuffer())
                    .then(buffer => zip.file(awemeName, buffer))
                    .then(() => msg_pre.textContent = `${index + 1}/${user_aweme_list.length} ` + awemeName)
            });
            Promise.all(promises).then(() => {
                return zip.generateAsync({type: "blob"})
            }).then((content) => {
                createDownloadLink(content, null, "zip", "【封面】");
                msg_pre.textContent = "封面打包完成";
                node.disabled = false;
            })
        } finally {
            node.disabled = false;
        }
    }

    async function downloadImg(node) {
        if (node.disabled) {
            alert("下载正在处理中，请不要重复点击按钮！");
            return;
        }
        node.disabled = true;
        try {
            const zip = new JSZip();
            let flag = true;
            let aweme_img_list = user_aweme_list.filter(a => a.images);
            for (let [i, aweme] of aweme_img_list.entries()) {
                let awemeName = getAwemeName(aweme);
                msg_pre.textContent = `${i + 1}/${aweme_img_list.length} ` + awemeName;
                let folder = zip.folder(awemeName);
                await Promise.all(aweme.images.map((link, index) => {
                    return fetch(link)
                        .then((res) => res.arrayBuffer())
                        .then((buffer) => {
                            folder.file(`image_${index + 1}.jpg`, buffer);
                        });
                }));
                flag = false;
            }
            if (flag) {
                alert("当前页面未发现图文链接");
                node.disabled = false;
                return;
            }
            msg_pre.textContent = "图文打包中...";
            zip.generateAsync({type: "blob"})
                .then((content) => {
                    createDownloadLink(content, null, "zip", "【图文】");
                    msg_pre.textContent = "图文打包完成";
                    node.disabled = false;
                });
        } finally {
            node.disabled = false;
        }
    }

    function douyinVideoDownloader() {
        const clonePlayclarity2Download = (xgPlayer, videoId, videoContainer) => {
            let playClarityDom = xgPlayer.querySelector('.xgplayer-playclarity-setting');
            if (!playClarityDom) return;
            let downloadDom = xgPlayer.querySelector(`.xgplayer-playclarity-setting[data-vid]`);
            const adjustMargin = (virtualDom) => {
                if (location.href.includes('search') && !location.href.includes('modal_id')) {
                    downloadDom.style.marginTop = "0px";
                    virtualDom.style.marginBottom = "37px";
                } else {
                    downloadDom.style.marginTop = "-68px";
                    virtualDom.style.marginBottom = "0px";
                }
            }
            if (downloadDom) {
                downloadDom.dataset.vid = videoId;
                videoContainer.dataset.vid = videoId;
                adjustMargin(downloadDom.querySelector('.virtual'));
                return;
            }
            downloadDom = playClarityDom.cloneNode(true);
            downloadDom.dataset.vid = videoId;
            videoContainer.dataset.vid = videoId;
            downloadDom.style = 'margin-top:-68px;padding-top:100px;';

            let downloadText = downloadDom.querySelector('.btn');
            if (!downloadText) return;
            downloadText.textContent = '工具';
            downloadText.style = 'font-size:14px;font-weight:600;';

            let virtualDom = downloadDom.querySelector('.virtual');
            if (!virtualDom) return;
            adjustMargin(virtualDom);
            downloadDom.onmouseover = () => virtualDom.style.display = 'block';
            downloadDom.onmouseout = () => virtualDom.style.display = 'none';
            virtualDom.innerHTML = '';
            let toLinkDom = createCommonElement("div", {style: "text-align:center;", class: "item"}, "打开视频源");
            virtualDom.appendChild(toLinkDom);
            toLinkDom.addEventListener('click', () => {
                let url = videoContainer && videoContainer.children.length > 0 && videoContainer.children[0].src
                    ? videoContainer.children[0].src : "";
                if (!url) {
                    let aweme = window.all_aweme_map.get(videoContainer.dataset.vid);
                    if (aweme) url = aweme.url;
                }
                //console.log('下载视频:', videoContainer.dataset.vid, url);
                if (url) window.open(url);
                else alert('未捕获到对应数据源！');
            });
            let copyDescDom = createCommonElement("div", {style: "text-align:center;", class: "item"}, "复制视频描述");
            virtualDom.appendChild(copyDescDom);
            copyDescDom.addEventListener('click', () => {
                let aweme = window.all_aweme_map.get(videoContainer.dataset.vid);
                if (!aweme) {
                    alert('未捕获到对应数据源！');
                } else if (!aweme.desc) {
                    alert('捕获的数据源，不含描述信息！');
                } else {
                    copyText(aweme.desc, copyDescDom);
                }
            })
            playClarityDom.after(downloadDom);
        }
        const run = (activeVideoElement) => {
            if (activeVideoElement === undefined) activeVideoElement = document.querySelector('#slidelist [data-e2e="feed-active-video"]');
            if (!activeVideoElement) return;
            const videoId = activeVideoElement.getAttribute('data-e2e-vid');
            let xgPlayer = activeVideoElement.querySelector('.xg-right-grid');
            if (!xgPlayer) return;
            //console.log('监听到切换视频:', videoId);
            clonePlayclarity2Download(xgPlayer, videoId, activeVideoElement.querySelector("video"));
        }
        const videoObserver = new MutationObserver((mutationsList, observer) => {
            for (let mutation of mutationsList) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'data-e2e') {
                    const newValue = mutation.target.getAttribute('data-e2e');
                    if (newValue === 'feed-active-video') run(mutation.target);
                }
            }
        });
        const rootObserver = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.id === 'slidelist') {
                        //console.log('检测到打开播放器，开始监听视频切换');
                        videoObserver.observe(node, {
                            attributes: true,
                            subtree: true,
                            attributeFilter: ['data-e2e']
                        });
                    }
                });
                mutation.removedNodes.forEach((node) => {
                    if (node.querySelector && node.querySelector('#slidelist')) {
                        //console.log('检测到关闭播放器，关闭监听...');
                        videoObserver.disconnect();
                    }
                });
            });
        });
        if (document.querySelector('#slidelist')) {
            //console.log('检测到打开播放器，开始监听视频切换');
            videoObserver.observe(document.querySelector('#slidelist'), {
                attributes: true,
                subtree: true,
                attributeFilter: ['data-e2e']
            });
        }
        rootObserver.observe(document.body, {childList: true, subtree: true});

        const checkVideoNode = () => {
            let playVideoElements = Array.from(document.querySelectorAll('video')).filter(v => v.autoplay);
            let videoContainer = location.href.includes('modal_id')
                ? playVideoElements[0]
                : playVideoElements[playVideoElements.length - 1];
            if (!videoContainer) return;
            let xgPlayer = videoContainer.parentNode.parentNode.querySelector('.xg-right-grid');
            if (!xgPlayer) return;

            let videoId;
            let sliderVideoDom = videoContainer.closest('#sliderVideo');
            if (sliderVideoDom) {
                videoId = sliderVideoDom.getAttribute('data-e2e-vid');
            } else {
                let detailVideoInfo = document.querySelector("[data-e2e='detail-video-info']");
                videoId = detailVideoInfo.getAttribute('data-e2e-aweme-id');
            }
            videoId = videoId ? videoId : new URLSearchParams(location.search).get('modal_id');
            if (videoId) clonePlayclarity2Download(xgPlayer, videoId, videoContainer)
        }
        // 全局播放器定时监听
        setInterval(checkVideoNode, 700);
    }

    if (document.title === "验证码中间页") return;
    createMsgBox();
    interceptResponse();
    douyinVideoDownloader();
    let domLoadedTimer;
    const checkElementLoaded = () => {
        const element = document.querySelector('#douyin-header-menuCt pace-island > div > div:nth-last-child(1) ul a');
        if (element) {
            //console.log('顶部栏加载完毕');
            msg_pre.textContent = "头像加载完成\n若需要下载用户数据，需进入目标用户主页\n若未捕获到数据，可以刷新重试";
            clearInterval(domLoadedTimer);
            domLoadedTimer = null;
            createAllButton();
            if (flag) flush();
        }
    };
    document.window = window;
    window.onload = () => {
        domLoadedTimer = setInterval(checkElementLoaded, 700);
    }
})();