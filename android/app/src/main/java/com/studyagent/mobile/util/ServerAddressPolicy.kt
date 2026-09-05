package com.studyagent.mobile.util

import java.net.URI

object ServerAddressPolicy {
    private val ipv4Pattern = Regex("^(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})$")

    fun normalize(input: String, allowPrivateHttp: Boolean): String {
        val raw = input.trim().trimEnd('/')
        require(raw.isNotEmpty()) { "请输入服务地址" }

        val uri = runCatching { URI(raw) }.getOrElse { throw IllegalArgumentException("服务地址格式不正确") }
        val scheme = uri.scheme?.lowercase()
        require(scheme == "https" || scheme == "http") { "服务地址必须以 https:// 或 http:// 开头" }
        require(uri.userInfo == null && uri.query == null && uri.fragment == null) { "服务地址不能包含账号、查询参数或锚点" }
        val host = uri.host?.lowercase() ?: throw IllegalArgumentException("服务地址缺少有效主机名")
        require(uri.port == -1 || uri.port in 1..65_535) { "服务地址端口必须在 1–65535 之间" }
        val path = uri.path.orEmpty().trimEnd('/')
        require(path.isEmpty() || path == "/api") { "服务地址只能填写站点根地址或 /api" }

        if (scheme == "http") {
            require(allowPrivateHttp && isPrivateOrLoopback(host)) {
                "正式版本只允许 HTTPS；调试版 HTTP 也仅限本机或私有局域网地址"
            }
        }

        val normalizedPath = if (path == "/api") "/api" else ""
        return URI(scheme, null, host, uri.port, normalizedPath, null, null).toString().trimEnd('/')
    }

    fun apiRoot(normalizedServer: String): String =
        if (normalizedServer.endsWith("/api")) normalizedServer else "$normalizedServer/api"

    internal fun isPrivateOrLoopback(host: String): Boolean {
        if (host == "localhost" || host == "::1" || host == "0:0:0:0:0:0:0:1") return true
        val match = ipv4Pattern.matchEntire(host) ?: return false
        val parts = match.groupValues.drop(1).map(String::toInt)
        if (parts.any { it !in 0..255 }) return false
        return parts[0] == 127 ||
            parts[0] == 10 ||
            parts[0] == 192 && parts[1] == 168 ||
            parts[0] == 172 && parts[1] in 16..31
    }
}
