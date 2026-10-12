// 黄果网页去广告：按请求域名保留原始选择器
const url = $request.url || "";
const contentType = Object.keys($response.headers || {}).find(k => k.toLowerCase() === "content-type");
const typeValue = contentType ? String($response.headers[contentType]) : "";

if (/^https:\/\/huangguo\.video/i.test(url) && /html/i.test(typeValue)) {
  $response.body = $response.body.replace(/<\/head>/i, '<style>div.hg-exo-slot,div.hg-exo-slot-list,.hg-tile-slot-list{display:none!important}</style></head>');
} else if (/^https:\/\/huangguoai\.com/i.test(url) && /html/i.test(typeValue)) {
  $response.body = $response.body.replace(/<\/head>/i, '<style>.hg-hero,.hg-ssp-slot,.hg-ssp-pause{display:none!important}</style></head>');
}

$done({ body: $response.body });
