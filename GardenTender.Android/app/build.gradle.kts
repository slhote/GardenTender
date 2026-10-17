import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.gardentender"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.gardentender"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        // Read through providers so Gradle tracks the file; otherwise the configuration cache keeps stale values.
        val localProps = Properties().apply {
            val file = rootProject.layout.projectDirectory.file("local.properties")
            val text = providers.fileContents(file)
                                .asText
            if (text.isPresent) load(text.get().reader())
        }
        val auth0Domain = localProps.getProperty("auth0.domain", "example.auth0.com")
        val auth0ClientId = localProps.getProperty("auth0.clientId", "")
        buildConfigField("String", "AUTH0_DOMAIN", "\"$auth0Domain\"")
        buildConfigField("String", "AUTH0_CLIENT_ID", "\"$auth0ClientId\"")
        // Must match the API identifier in Auth0; without it Auth0 issues an opaque token the API can't verify.
        val auth0Audience = localProps.getProperty("auth0.audience", "https://api.gardentender")
        // 10.0.2.2 reaches the host machine from the emulator; set api.baseUrl to your PC's LAN IP for a real phone.
        val apiBaseUrl = localProps.getProperty("api.baseUrl", "http://10.0.2.2:8000")
        buildConfigField("String", "AUTH0_AUDIENCE", "\"$auth0Audience\"")
        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")
        manifestPlaceholders["auth0Domain"] = auth0Domain
        manifestPlaceholders["auth0Scheme"] = "gardentender-auth"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.extended)
    implementation(libs.androidx.camera.core)
    implementation(libs.androidx.camera.camera2)
    implementation(libs.androidx.camera.lifecycle)
    implementation(libs.androidx.camera.view)
    implementation(libs.mlkit.barcode.scanning)
    implementation(libs.zxing.core)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.process)
    implementation(libs.auth0)
    implementation(libs.androidx.biometric)
    implementation(libs.androidx.work.runtime)
    implementation(libs.koin.android)
    implementation(libs.koin.compose)
}
