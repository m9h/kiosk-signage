package org.mhough.kiosk;

import android.content.Context;
import android.view.Gravity;
import android.view.View;
import android.widget.FrameLayout;

/**
 * Shows its one child turned by 0, 90, 180 or 270 degrees inside a display that
 * stays landscape. Rotating the whole display instead (wm user-rotation) works
 * in a screenshot but scrambles the Fire TV Stick 4K Max's HDMI output.
 */
public class RotatedFrame extends FrameLayout {
    private int degrees;

    public RotatedFrame(Context context) {
        super(context);
    }

    public void setDegrees(int degrees) {
        this.degrees = ((degrees % 360) + 360) % 360;
        requestLayout();
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        post(this::fit);
    }

    @Override
    public void requestLayout() {
        super.requestLayout();
        if (getWidth() > 0) {
            post(this::fit);
        }
    }

    private void fit() {
        if (getChildCount() == 0) {
            return;
        }
        View child = getChildAt(0);
        boolean quarter = degrees == 90 || degrees == 270;
        int w = quarter ? getHeight() : getWidth();
        int h = quarter ? getWidth() : getHeight();
        LayoutParams lp = (LayoutParams) child.getLayoutParams();
        if (lp.width != w || lp.height != h || child.getRotation() != degrees) {
            child.setLayoutParams(new LayoutParams(w, h, Gravity.CENTER));
            child.setRotation(degrees);
        }
    }
}
