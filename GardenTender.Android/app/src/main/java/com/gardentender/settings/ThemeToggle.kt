package com.gardentender.settings

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Pill toggle showing a sun/"LIGHT MODE" or moon/"DARK MODE" state. */
@Composable
fun ThemeToggle(dark: Boolean, onChange: (Boolean) -> Unit) {
    val trackColor by animateColorAsState(if (dark) Color(0xFF2E3138) else Color(0xFFEDEDED), label = "track")
    val thumbOffset by animateDpAsState(if (dark) 64.dp else 0.dp, label = "thumb")
    val textColor = if (dark) Color(0xFF6B6F78) else Color(0xFFB0B3BA)
    val iconColor = Color(0xFFA9AEB8)
    Box(
        Modifier
            .size(104.dp, 40.dp)
            .clip(CircleShape)
            .background(trackColor)
            .toggleable(dark, role = Role.Switch, onValueChange = onChange)
            .padding(4.dp),
    ) {
        Text(
            if (dark) "DARK" else "LIGHT",
            modifier = Modifier.align(if (dark) Alignment.CenterStart else Alignment.CenterEnd).padding(horizontal = 8.dp),
            color = textColor,
            fontWeight = FontWeight.ExtraBold,
            fontSize = 9.sp,
            lineHeight = 10.sp,
            textAlign = TextAlign.Center,
        )
        Box(
            Modifier.offset(x = thumbOffset).size(32.dp).clip(CircleShape).background(Color.White),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                if (dark) Icons.Filled.DarkMode else Icons.Filled.LightMode,
                contentDescription = null,
                tint = iconColor,
                modifier = Modifier.size(20.dp),
            )
        }
    }
}
