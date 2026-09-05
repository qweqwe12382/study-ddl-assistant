package com.studyagent.mobile.data

import com.studyagent.mobile.util.ServerAddressPolicy
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpCookie
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets
import java.util.Arrays

class ApiException(
    val statusCode: Int,
    override val message: String,
) : Exception(message)

class ApiClient {
    private data class SessionCookie(val value: String, val secure: Boolean)

    private val cookies = linkedMapOf<String, SessionCookie>()
    private var apiRoot: String = ""

    fun configure(normalizedServer: String) {
        val nextRoot = ServerAddressPolicy.apiRoot(normalizedServer)
        if (nextRoot != apiRoot) cookies.clear()
        apiRoot = nextRoot
    }

    fun clearSession() {
        cookies.clear()
    }

    suspend fun login(email: String, password: String): UserProfile {
        val payload = JSONObject().put("email", email).put("password", password).toString()
        return request("POST", "/auth/login", payload).toUserProfile()
    }

    suspend fun currentUser(): UserProfile = request("GET", "/auth/me").toUserProfile()

    suspend fun dashboard(): Dashboard = request("GET", "/dashboard").toDashboard()

    suspend fun tasks(): List<TaskItem> =
        requestArray("GET", "/tasks").objects().map(JSONObject::toTaskItem)

    suspend fun academicOverview(week: Int): AcademicOverview =
        request("GET", "/academic-calendar/overview?week=$week").toAcademicOverview()

    suspend fun completeTask(task: TaskItem): TaskItem {
        val tag = task.navigationKey?.let { "\"$it:${task.revision}\"" }
        return request("POST", "/tasks/${task.id}/complete", "{}", tag).toTaskItem()
    }

    suspend fun logout() {
        try {
            request("POST", "/auth/logout", "{}", expectNoContent = true)
        } finally {
            clearSession()
        }
    }

    private suspend fun requestArray(method: String, path: String, body: String? = null): JSONArray =
        JSONArray(requestText(method, path, body))

    private suspend fun request(
        method: String,
        path: String,
        body: String? = null,
        ifMatch: String? = null,
        expectNoContent: Boolean = false,
    ): JSONObject {
        val text = requestText(method, path, body, ifMatch)
        if (expectNoContent || text.isBlank()) return JSONObject()
        return JSONObject(text)
    }

    private suspend fun requestText(
        method: String,
        path: String,
        body: String? = null,
        ifMatch: String? = null,
    ): String = withContext(Dispatchers.IO) {
        check(apiRoot.isNotBlank()) { "尚未配置服务地址" }
        val url = URL("$apiRoot$path")
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = method
            instanceFollowRedirects = false
            connectTimeout = 12_000
            readTimeout = 18_000
            setRequestProperty("Accept", "application/json")
            setRequestProperty("Accept-Charset", "utf-8")
            sessionCookieHeader(url.protocol == "https")?.let { setRequestProperty("Cookie", it) }
            if (method !in setOf("GET", "HEAD", "OPTIONS")) {
                cookies[CSRF_COOKIE]?.value?.let { setRequestProperty("X-CSRF-Token", it) }
            }
            ifMatch?.let { setRequestProperty("If-Match", it) }
        }

        var bodyBytes: ByteArray? = null
        try {
            if (body != null) {
                bodyBytes = body.toByteArray(StandardCharsets.UTF_8)
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.setFixedLengthStreamingMode(bodyBytes.size)
                connection.outputStream.use { it.write(bodyBytes) }
            }

            val status = connection.responseCode
            captureSessionCookies(connection)
            val stream = if (status >= 400) connection.errorStream else connection.inputStream
            val response = stream?.use(::readLimitedUtf8).orEmpty()
            if (status == HttpURLConnection.HTTP_UNAUTHORIZED) clearSession()
            if (status !in 200..299) throw ApiException(status, errorMessage(response, status))
            response
        } finally {
            bodyBytes?.let { Arrays.fill(it, 0) }
            connection.disconnect()
        }
    }

    private fun sessionCookieHeader(isHttps: Boolean): String? {
        val values = cookies.entries.mapNotNull { (name, cookie) ->
            if (cookie.secure && !isHttps) null else "$name=${cookie.value}"
        }
        return values.takeIf { it.isNotEmpty() }?.joinToString("; ")
    }

    private fun captureSessionCookies(connection: HttpURLConnection) {
        connection.headerFields.entries
            .filter { (name, _) -> name?.equals("Set-Cookie", ignoreCase = true) == true }
            .flatMap { it.value.orEmpty() }
            .forEach { raw ->
                runCatching { HttpCookie.parse(raw) }.getOrDefault(emptyList()).forEach { cookie ->
                    if (cookie.name !in ALLOWED_COOKIES) return@forEach
                    if (cookie.maxAge == 0L || cookie.value.isBlank()) cookies.remove(cookie.name)
                    else cookies[cookie.name] = SessionCookie(cookie.value, cookie.secure)
                }
            }
    }

    private fun readLimitedUtf8(stream: java.io.InputStream): String {
        val output = ByteArrayOutputStream()
        val buffer = ByteArray(8 * 1024)
        var total = 0
        while (true) {
            val read = stream.read(buffer)
            if (read < 0) break
            total += read
            if (total > MAX_RESPONSE_BYTES) throw ApiException(502, "服务响应过大，已停止读取")
            output.write(buffer, 0, read)
        }
        return output.toString(StandardCharsets.UTF_8.name())
    }

    private fun errorMessage(body: String, status: Int): String {
        val parsed = runCatching { JSONObject(body) }.getOrNull()
        val detail = parsed?.opt("detail")
        val error = parsed?.optJSONObject("error")
        return when (detail) {
            is JSONObject -> detail.optString("message").ifBlank { "请求失败（$status）" }
            is String -> detail.ifBlank { "请求失败（$status）" }
            else -> error?.optString("message")?.ifBlank { null } ?: "请求失败（$status）"
        }
    }

    private companion object {
        const val SESSION_COOKIE = "study_session"
        const val CSRF_COOKIE = "study_csrf"
        const val MAX_RESPONSE_BYTES = 4 * 1024 * 1024
        val ALLOWED_COOKIES = setOf(SESSION_COOKIE, CSRF_COOKIE)
    }
}
