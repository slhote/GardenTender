package com.gardentender.chat

import android.app.Activity
import android.app.Application
import android.os.Bundle
import java.lang.ref.WeakReference

/**
 * Remembers the activity currently on screen so external screens (like the calendar editor) can be launched
 * from it. Launching from the application context needs FLAG_ACTIVITY_NEW_TASK, which makes other apps
 * reuse an old task and show a stale screen instead of the new event.
 */
class ActivityTracker : Application.ActivityLifecycleCallbacks {
    private var ref = WeakReference<Activity>(null)

    val current: Activity? get() = ref.get()

    override fun onActivityResumed(activity: Activity) { ref = WeakReference(activity) }
    override fun onActivityPaused(activity: Activity) { if (ref.get() === activity) ref = WeakReference(null) }
    override fun onActivityCreated(activity: Activity, savedInstanceState: Bundle?) {}
    override fun onActivityStarted(activity: Activity) {}
    override fun onActivityStopped(activity: Activity) {}
    override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) {}
    override fun onActivityDestroyed(activity: Activity) {}
}
