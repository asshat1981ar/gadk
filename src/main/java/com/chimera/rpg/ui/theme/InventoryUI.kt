package com.chimera.rpg.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.chimera.rpg.ui.theme.RPGTheme
import com.chimera.rpg.ui.theme.surface

/**
 * InventoryUI displays a grid of item slots with category filtering.
 * Supports drag-and-drop placeholders via mutable state.
 */
@Composable
fun InventoryUI(
    modifier: Modifier = Modifier,
    onItemDrop: ((Int, Int) -> Unit)? = null
) {
    val inventorySlots = remember {
        mutableStateListOf(*Array(36) { "" }.toTypedArray())
    }
    
    val categories = InventoryCategory.entries
    var selectedCategory by remember { mutableStateOf(categories.first()) }

    Column {
        // Category tabs
        SingleChoiceSegmentedButtonRow(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
        ) {
            categories.forEachIndexed { index, category ->
                SegmentedButton(
                    selected = selectedCategory == category,
                    onClick = { selectedCategory = category },
                    shape = SegmentedButtonDefaults.itemShape(
                        index = index,
                        count = categories.size
                    )
                ) {
                    Text(text = category.name)
                }
            }
        }

        Box(
            modifier = modifier.fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            LazyVerticalGrid(
                columns = GridCells.Fixed(6),
                modifier = Modifier.padding(16.dp)
            ) {
                items(inventorySlots.size) { index ->
                    InventorySlot(
                        itemName = inventorySlots[index],
                        index = index,
                        categoryFilter = selectedCategory,
                        onDrop = onItemDrop?.let { onDrop ->
                            { itemId -> onDrop(index, itemId) }
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun InventorySlot(
    itemName: String,
    index: Int,
    categoryFilter: InventoryCategory,
    onDrop: ((Int) -> Unit)? = null
) {
    val slotSize = 64.dp.toPx()
    
    // Filter items by category
    val shouldShow = itemName.isEmpty() || categoryFilter == InventoryCategory.ALL
    
    Box(
        modifier = Modifier
            .padding(4.dp)
            .selectable(
                selected = itemName.isNotEmpty(),
                onClick = { onDrop?.invoke(index) }
            )
            .fillMaxSize()
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            if (shouldShow) {
                // Slot background
                drawRect(
                    color = if (itemName.isNotEmpty()) surface else Color(0xFF2A2A2C),
                    topLeft = Offset.Zero,
                    size = Size(slotSize, slotSize),
                    style = Stroke(width = if (itemName.isNotEmpty()) 2f else 1f)
                )

                if (itemName.isNotEmpty()) {
                    // Draw item icon (simple circle with letter)
                    drawCircle(
                        color = Color(0xFF66BB6A),
                        radius = slotSize / 2 - 4,
                        center = Offset(slotSize / 2, slotSize / 2)
                    )
                    drawContext.canvas.nativeCanvas.apply {
                        val paint = android.graphics.Paint().apply {
                            color = android.graphics.Color.BLACK
                            textSize = 28f
                            textAlign = android.graphics.Paint.Align.CENTER
                        }
                        drawText(
                            itemName.take(1),
                            slotSize / 2,
                            slotSize / 2 + 10,
                            paint
                        )
                    }
                }
            } else {
                // Draw empty/filtered slot with dimmed appearance
                drawRect(
                    color = Color(0xFF1A1A1C).copy(alpha = 0.5f),
                    topLeft = Offset.Zero,
                    size = Size(slotSize, slotSize),
                    style = Stroke(width = 1f)
                )
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun InventoryUIPreview() {
    RPGTheme {
        InventoryUI()
    }
}