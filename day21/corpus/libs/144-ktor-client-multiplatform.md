# Creating a cross-platform mobile application

Creating a cross-platform mobile application | Ktor Documentation

### Ktor 3.6.0 Help

# Creating a cross-platform mobile application

The Ktor HTTP client can be used in multiplatform projects. In this tutorial, we'll create a simple Kotlin Multiplatform Mobile application, which sends a request and receives a response body as plain HTML text.

## Prerequisites

First, you need to set up an environment for cross-platform mobile development by installing the necessary tools on a suitable operating system. Learn how to do this from the Set up an environment section.

You will need a Mac with macOS to complete certain steps in this tutorial, which include writing iOS-specific code and running an iOS application.

## Create a new project

To create a new project, you can use the Kotlin Multiplatform project wizard in IntelliJ IDEA. It will create a basic multiplatform project which you can expand with clients and services.

Launch IntelliJ IDEA.

In IntelliJ IDEA, select File | New | Project.

In the panel on the left, select Kotlin Multiplatform.

Specify the following fields in the New Project window:

Name: KmpKtor

Group: com.example.ktor 

Select Android and iOS targets.

For iOS, select the Do not share UI option to keep the UI native.

Click the Create button and wait for the IDE to generate and import the project.

## Configure build scripts

### Add Ktor dependencies

To use the Ktor HTTP client in your project, you need to add at least two dependencies: a client dependency and an engine dependency.

Open the gradle/libs.versions.toml file add the Ktor version:

[versions]
ktor = "3.6.0"

In the same gradle/libs.versions.toml define the Ktor client and engine libraries:

[libraries]
ktor-client-core = { module = "io.ktor:ktor-client-core", version.ref = "ktor" }
ktor-client-okhttp = { module = "io.ktor:ktor-client-okhttp", version.ref = "ktor" }
ktor-client-darwin = { module = "io.ktor:ktor-client-darwin", version.ref = "ktor" }

Open the shared/build.gradle.kts file and add the following dependencies:

 sourceSets {
 commonMain.dependencies {
 implementation(libs.ktor.client.core)
 }
 androidMain.dependencies {
 implementation(libs.ktor.client.okhttp)
 }
 iosMain.dependencies {
 implementation(libs.ktor.client.darwin)
 }
 }

Add the ktor-client-core to the commonMain source set to enable Ktor client functionality in shared code.

In the androidMain source set, include the ktor-client-okhttp dependency to use the OkHttp engine on Android. Alternatively, you can choose from other available Android/JVM engines.

In the iosMain source set, add the ktor-client-darwin dependency to use the Darwin engine on iOS.

### Add coroutines

To use coroutines in Android code, you need to add kotlinx.coroutines to your project:

Open the gradle/libs.versions.toml file and specify the coroutines version and libraries:

[versions]
kotlinx-coroutines = "1.11.0"

[libraries]
kotlinx-coroutines-core = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-core", version.ref = "kotlinx-coroutines" }
kotlinx-coroutines-android = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-android", version.ref = "kotlinx-coroutines" }

Open the shared/build.gradle.kts file and add the kotlinx-coroutines-core dependency to the commonMain source set:

 sourceSets {
 commonMain.dependencies {
 implementation(libs.ktor.client.core)
 implementation(libs.kotlinx.coroutines.core)
 }
 }

Then, open the composeApp/build.gradle.kts file and add the kotlinx-coroutines-android dependency to the androidMain source set:

 sourceSets {
 androidMain.dependencies {
 // ...
 implementation(libs.kotlinx.coroutines.android)
 }
 }

Select Build | Sync Project with Gradle Files to install the added dependencies.

## Update your application

### Shared code

To update the code shared between Android and iOS, open the shared/src/commonMain/kotlin/com/example/ktor/kmpktor/Greeting.kt file and add the following code to the Greeting class:

package com.example.ktor.kmpktor

import io.ktor.client.HttpClient
import io.ktor.client.request.get
import io.ktor.client.statement.bodyAsText

class Greeting {
 private val client = HttpClient()

 suspend fun greet(): String {
 val response = client.get("https://ktor.io/docs/")
 return response.bodyAsText()
 }
}

The HttpClient constructor creates the HTTP client.

The suspending greet() function makes a request and receives the body of a response as a string value.

### Android code

Open the composeApp/src/androidMain/kotlin/com/example/ktor/kmpktor/App.kt file and update the code as follows:

package com.example.ktor.kmpktor

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.safeContentPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
@Preview
fun App() {
 MaterialTheme {
 Column(
 modifier = Modifier
 .background(MaterialTheme.colorScheme.primaryContainer)
 .safeContentPadding()
 .fillMaxSize(),
 horizontalAlignment = Alignment.CenterHorizontally,
 ) {
 var text by remember { mutableStateOf("Loading") }
 LaunchedEffect(true) {
 text = try {
 Greeting().greet()
 } catch (e: Exception) {
 e.message ?: "error"
 }
 }
 GreetingView(text)
 }
 }
}

@Composable
fun GreetingView(text: String) {
 Text(text = text)
}

@Preview
@Composable
fun DefaultPreview() {
 MaterialTheme {
 GreetingView("Hello, Android!")
 }
}

LaunchedEffect() launches a coroutine tied to the composable’s lifecycle. Within this coroutine, the shared greet() function is called, its result is assigned to text, and any exceptions are caught and handled.

### iOS code

Open the iosApp/iosApp/ContentView.swift file and update the code in the following way:

import SwiftUI
import Shared

struct ContentView: View {
 @StateObject private var viewModel = ViewModel()

 var body: some View {
 Text(viewModel.text)
 }
}

extension ContentView {
 @MainActor
 class ViewModel: ObservableObject {
 @Published var text = "Loading..."
 init() {
 Greeting().greet { greeting, error in
 if let greeting = greeting {
 self.text = greeting
 } else {
 self.text = error?.localizedDescription ?? "error"
 }
 }
 }
 }
}

On iOS, the greet() suspending function is available as a function with a callback.

## Enable internet access on Android

The final step is to enable internet access for the Android application. Open the composeApp/src/androidMain/AndroidManifest.xml file and enable the required permission using the &lt;uses-permission&gt; element:

<manifest>
 <uses-permission android:name="android.permission.INTERNET" />
 <application>
 ...
 </application>
</manifest> 

## Run your application on Android

In IntelliJ IDEA, select composeApp in the list of run configurations.

Choose an Android virtual device next to the list of configurations and click Run. 

If you don't have a device in the list, create a new Android virtual device.

Once loaded, the simulator should display the received HTML document as plain text. 

If your Android emulator cannot connect to the internet, try performing a cold boot. In the Device Manager tool window, click the ⋮ (three dots) next to a stopped device and select Cold Boot from the menu. This often helps clear corrupted emulator caches that can cause connectivity issues.

## Run your application on iOS

In IntelliJ IDEA, select iosApp in the list of run configurations.

Choose an iOS simulated device next to the list of configurations and click Run. 

If you don't have an available iOS configuration in the list, add a new run configuration.

Once loaded, the simulator should display the received HTML document as plain text. 

03 November 2025

Create a client applicationSupported platforms
