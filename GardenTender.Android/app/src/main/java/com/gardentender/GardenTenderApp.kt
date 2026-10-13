package com.gardentender

import android.app.Application
import com.gardentender.di.appModule
import org.koin.android.ext.koin.androidContext
import org.koin.core.context.startKoin

class GardenTenderApp : Application() {
    override fun onCreate() {
        super.onCreate()
        startKoin {
            androidContext(this@GardenTenderApp)
            modules(appModule)
        }
    }
}
