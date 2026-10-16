package com.gardentender

import android.app.Application
import com.gardentender.di.appModule
import org.koin.android.ext.koin.androidContext
import org.koin.core.context.GlobalContext
import org.koin.core.context.startKoin
import com.gardentender.chat.ActivityTracker

class GardenTenderApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // Chat is memory-only now; remove the file older builds saved.
        java.io.File(filesDir, "chat.json").delete()
        startKoin {
            androidContext(this@GardenTenderApp)
            modules(appModule)
        }
        registerActivityLifecycleCallbacks(GlobalContext.get().get<ActivityTracker>())
    }
}
