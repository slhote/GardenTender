package com.gardentender

import android.app.Application
import com.gardentender.chat.ActivityTracker
import com.gardentender.di.appModule
import org.koin.android.ext.koin.androidContext
import org.koin.core.context.startKoin

class GardenTenderApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // Chat is memory-only now; remove the file older builds saved.
        java.io.File(filesDir, "chat.json").delete()
        val koin = startKoin {
            androidContext(this@GardenTenderApp)
            modules(appModule)
        }.koin
        registerActivityLifecycleCallbacks(koin.get<ActivityTracker>())
    }
}
