// 2048AI：对指定 API 返回 HTTP 200 的空 JSON 对象
$done({
  response: {
    status: 200,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store"
    },
    body: "{}"
  }
});
