package com.studyagent.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.viewmodel.compose.viewModel
import com.studyagent.mobile.data.StudyRepository
import com.studyagent.mobile.ui.AppViewModel
import com.studyagent.mobile.ui.StudyAgentApp
import com.studyagent.mobile.ui.theme.StudyAgentTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val repository = StudyRepository(applicationContext)
        setContent {
            StudyAgentTheme {
                val appViewModel: AppViewModel = viewModel(factory = AppViewModel.Factory(repository))
                StudyAgentApp(appViewModel)
            }
        }
    }
}
