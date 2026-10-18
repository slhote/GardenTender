package com.gardentender.chat

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

@Composable
fun ChatFab(onClick: () -> Unit, modifier: Modifier = Modifier) {
    FloatingActionButton(onClick = onClick, modifier = modifier) {
        Icon(Icons.Filled.Chat, contentDescription = "Open chat")
    }
}

/** Right-side modal sheet with a scrim; tapping the scrim or the close button dismisses it. */
@Composable
fun ChatSideSheet(vm: ChatViewModel, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxSize()) {
        AnimatedVisibility(visible = vm.open, enter = fadeIn(), exit = fadeOut()) {
            Box(
                Modifier
                    .fillMaxSize()
                    .background(Color.Black.copy(alpha = 0.4f))
                    .clickable(
                        interactionSource = remember { MutableInteractionSource() },
                        indication = null,
                        onClick = vm::hide,
                    ),
            )
        }
        AnimatedVisibility(
            visible = vm.open,
            modifier = Modifier.align(Alignment.CenterEnd),
            enter = slideInHorizontally { it },
            exit = slideOutHorizontally { it },
        ) {
            Surface(
                modifier = Modifier.fillMaxHeight().fillMaxWidth(0.9f).widthIn(max = 420.dp),
                color = MaterialTheme.colorScheme.surface,
                tonalElevation = 3.dp,
                shape = RoundedCornerShape(topStart = 28.dp, bottomStart = 28.dp),
            ) {
                ChatContent(vm)
            }
        }
    }
}

@Composable
private fun ChatContent(vm: ChatViewModel) {
    var input by rememberSaveable { mutableStateOf("") }
    val listState = rememberLazyListState()
    LaunchedEffect(vm.messages.size, vm.open) {
        if (vm.messages.isNotEmpty()) listState.scrollToItem(vm.messages.lastIndex)
    }
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding()) {
        Row(
            Modifier.fillMaxWidth().padding(start = 16.dp, end = 4.dp, top = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Chat", style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
            IconButton(onClick = vm::hide) { Icon(Icons.Filled.Close, contentDescription = "Close chat") }
        }
        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(vm.messages) { MessageBubble(it) }
            if (vm.sending) item { Text("…", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
        if (vm.pending.isNotEmpty()) ConfirmCard(vm)
        Row(
            Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                modifier = Modifier.weight(1f),
                enabled = vm.pending.isEmpty(),
                placeholder = { Text("Message") },
                leadingIcon = { ModelMenu(vm) },
                maxLines = 4,
            )
            IconButton(
                onClick = { vm.send(input); input = "" },
                enabled = input.isNotBlank() && !vm.sending && vm.pending.isEmpty(),
            ) { Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send") }
        }
    }
}

/** Menu button inside the input field for choosing which LLM the API uses. */
@Composable
private fun ModelMenu(vm: ChatViewModel) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        IconButton(onClick = { expanded = true }, enabled = !vm.sending) {
            Icon(Icons.Filled.Tune, contentDescription = "Model: ${vm.model}")
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            CHAT_MODELS.forEach { name ->
                DropdownMenuItem(
                    text = { Text(name) },
                    leadingIcon = { if (name == vm.model) Icon(Icons.Filled.Check, contentDescription = "Selected") },
                    onClick = { vm.selectModel(name); expanded = false },
                )
            }
        }
    }
}

/** The server is paused on these tool calls; nothing runs until the user answers. */
@Composable
private fun ConfirmCard(vm: ChatViewModel) {
    Card(Modifier.fillMaxWidth().padding(horizontal = 12.dp)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Allow this action?", style = MaterialTheme.typography.titleSmall)
            vm.pending.forEach { call ->
                Text(describeCall(call), style = MaterialTheme.typography.bodyMedium)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { vm.decide(true) }, enabled = !vm.sending) { Text("Approve") }
                OutlinedButton(onClick = { vm.decide(false) }, enabled = !vm.sending) { Text("Decline") }
            }
        }
    }
}

@Composable
private fun MessageBubble(message: ChatMessage) {
    val scheme = MaterialTheme.colorScheme
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = if (message.fromUser) Arrangement.End else Arrangement.Start,
    ) {
        Surface(
            color = if (message.fromUser) scheme.primaryContainer else scheme.surfaceVariant,
            contentColor = if (message.fromUser) scheme.onPrimaryContainer else scheme.onSurfaceVariant,
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.widthIn(max = 300.dp),
        ) {
            Text(message.text, Modifier.padding(horizontal = 12.dp, vertical = 8.dp))
        }
    }
}
