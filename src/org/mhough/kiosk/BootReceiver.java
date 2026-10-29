package org.mhough.kiosk;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.SystemClock;

/**
 * Brings the kiosk up after boot and after the app is updated, START_DELAY_MS
 * later rather than at once: a kiosk that comes up immediately covers the
 * "Allow USB debugging?" prompt, which cannot then be answered.
 */
public class BootReceiver extends BroadcastReceiver {
    private static final long START_DELAY_MS = 3 * 60 * 1000L;

    @Override
    public void onReceive(Context context, Intent intent) {
        Intent start = new Intent(context, KioskActivity.class);
        start.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
        PendingIntent pi = PendingIntent.getActivity(context, 0, start,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        AlarmManager am = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        // Exact: a plain set() was deferred to ~6.5 min after boot on Fire OS 8.
        am.setExactAndAllowWhileIdle(AlarmManager.ELAPSED_REALTIME_WAKEUP,
                SystemClock.elapsedRealtime() + START_DELAY_MS, pi);
    }
}
