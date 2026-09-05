package com.studyagent.mobile.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class ServerAddressPolicyTest {
    @Test
    fun `https origin is normalized and api root is added`() {
        val normalized = ServerAddressPolicy.normalize("https://Study.Example.com:8443/", false)

        assertEquals("https://study.example.com:8443", normalized)
        assertEquals("https://study.example.com:8443/api", ServerAddressPolicy.apiRoot(normalized))
    }

    @Test
    fun `existing api root remains stable`() {
        val normalized = ServerAddressPolicy.normalize("https://study.example.com/api", false)

        assertEquals("https://study.example.com/api", normalized)
        assertEquals(normalized, ServerAddressPolicy.apiRoot(normalized))
    }

    @Test
    fun `release policy rejects all cleartext servers`() {
        val error = assertThrows(IllegalArgumentException::class.java) {
            ServerAddressPolicy.normalize("http://127.0.0.1:8000", false)
        }

        assertTrue(error.message.orEmpty().contains("HTTPS"))
    }

    @Test
    fun `debug policy accepts only loopback or private cleartext hosts`() {
        assertEquals(
            "http://127.0.0.1:8000",
            ServerAddressPolicy.normalize("http://127.0.0.1:8000", true),
        )
        assertEquals(
            "http://192.168.1.8:8000",
            ServerAddressPolicy.normalize("http://192.168.1.8:8000", true),
        )
        assertThrows(IllegalArgumentException::class.java) {
            ServerAddressPolicy.normalize("http://example.com", true)
        }
    }

    @Test
    fun `credentials query fragments and arbitrary paths are rejected`() {
        listOf(
            "https://user:pass@example.com",
            "https://example.com?next=evil",
            "https://example.com/#fragment",
            "https://example.com/other",
            "https://example.com:99999",
        ).forEach { value ->
            assertThrows(value, IllegalArgumentException::class.java) {
                ServerAddressPolicy.normalize(value, true)
            }
        }
    }
}
