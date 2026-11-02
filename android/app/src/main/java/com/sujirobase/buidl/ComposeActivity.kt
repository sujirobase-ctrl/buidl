package com.sujirobase.buidl

import android.Manifest
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.DocumentsContract
import android.webkit.CookieManager
import android.webkit.WebStorage
import android.widget.VideoView
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.compose.LocalActivity
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.rounded.Collections
import androidx.compose.material.icons.rounded.DarkMode
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.Folder
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.LightMode
import androidx.compose.material.icons.rounded.MoreVert
import androidx.compose.material.icons.rounded.MoreHoriz
import androidx.compose.material.icons.rounded.Pause
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.Locale

private val DarkColors = darkColorScheme(
    primary = Color(0xFFE7B5FF), onPrimary = Color(0xFF43205A),
    primaryContainer = Color(0xFF5B386F), onPrimaryContainer = Color(0xFFF4DAFF),
    background = Color(0xFF1B1B1F), surface = Color(0xFF1B1B1F),
    surfaceContainer = Color(0xFF26262E), outline = Color(0xFF929099),
)
private val LightColors = lightColorScheme(
    primary = Color(0xFF77558C), onPrimary = Color.White,
    primaryContainer = Color(0xFFF1D9FF), onPrimaryContainer = Color(0xFF2C0B42),
    background = Color(0xFFFFF7FF), surface = Color(0xFFFFF7FF),
    surfaceContainer = Color(0xFFF2ECF4), outline = Color(0xFF79747E),
)

private enum class Destination(val label: String, val icon: ImageVector) {
    DOWNLOAD("Início", Icons.Rounded.Home),
    GALLERY("Downloads", Icons.Rounded.Download),
    FILES("Mais", Icons.Rounded.MoreHoriz),
}

private data class MediaItem(
    val index: Int,
    val name: String,
    val kind: String,
    val post: String,
    val host: String,
    val origin: String,
)

class ComposeActivity : ComponentActivity() {
    lateinit var model: AppModel

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        model = (application as BuidlApplication).model
        setContent { BuidlApp(model) }
    }

    fun runService(action: String, configure: Intent.() -> Unit = {}) {
        val intent = Intent(this, DownloadService::class.java).setAction(action).apply(configure)
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent) else startService(intent)
    }
}

@Composable
private fun BuidlApp(model: AppModel) {
    val activity = LocalActivity.current as ComposeActivity
    val prefs = remember { activity.getSharedPreferences("buidl", android.content.Context.MODE_PRIVATE) }
    var appearance by rememberSaveable { mutableIntStateOf(prefs.getInt("appearance", 2)) }
    val systemDark = androidx.compose.foundation.isSystemInDarkTheme()
    val dark = appearance == 2 || appearance == 0 && systemDark
    val colors = if (Build.VERSION.SDK_INT >= 31) {
        if (dark) dynamicDarkColorScheme(activity) else dynamicLightColorScheme(activity)
    } else if (dark) DarkColors else LightColors
    MaterialTheme(colorScheme = colors) {
        var destination by rememberSaveable { mutableStateOf(Destination.DOWNLOAD) }
        var snapshotText by remember { mutableStateOf(model.snapshot.toString()) }
        var itemsText by remember { mutableStateOf(model.items.toString()) }
        LaunchedEffect(Unit) {
            while (true) {
                snapshotText = model.snapshot.toString()
                itemsText = model.items.toString()
                delay(350)
            }
        }
        val snapshot = remember(snapshotText) { JSONObject(snapshotText) }
        val media = remember(itemsText) { parseMedia(itemsText) }
        val snackbar = remember { SnackbarHostState() }
        val scope = rememberCoroutineScope()
        val message: (String) -> Unit = { scope.launch { snackbar.showSnackbar(it) } }
        val navigation: @Composable (Boolean) -> Unit = { rail ->
            if (rail) NavigationRail(modifier = Modifier.fillMaxHeight()) {
                Spacer(Modifier.height(12.dp))
                Destination.entries.forEach { item ->
                    NavigationRailItem(
                        selected = destination == item,
                        onClick = { destination = item },
                        icon = { Icon(item.icon, null) }, label = { Text(item.label) },
                    )
                }
            } else NavigationBar {
                Destination.entries.forEach { item ->
                    NavigationBarItem(
                        selected = destination == item,
                        onClick = { destination = item },
                        icon = { Icon(item.icon, null) }, label = { Text(item.label) },
                    )
                }
            }
        }

        androidx.compose.foundation.layout.BoxWithConstraints(Modifier.fillMaxSize()) {
            val expanded = maxWidth >= 840.dp
            Scaffold(
                modifier = Modifier.fillMaxSize(),
                snackbarHost = { SnackbarHost(snackbar) },
                bottomBar = { if (!expanded) navigation(false) },
                contentWindowInsets = WindowInsets.safeDrawing,
            ) { padding ->
                Row(
                    Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .consumeWindowInsets(padding)
                ) {
                    if (expanded) navigation(true)
                    when (destination) {
                        Destination.DOWNLOAD -> DownloadScreen(model, snapshot, prefs, appearance, { value ->
                            appearance = value
                            prefs.edit().putInt("appearance", value).apply()
                        }, message) { destination = Destination.GALLERY }
                        Destination.GALLERY -> GalleryScreen(model, snapshot, media, message)
                        Destination.FILES -> FilesScreen(model, snapshot, message) { destination = Destination.DOWNLOAD }
                    }
                }
            }
        }
    }
}

@Composable
private fun ScreenTitle(title: String, subtitle: String) {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun SectionCard(content: @Composable ColumnScope.() -> Unit) {
    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.elevatedCardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer),
        shape = RoundedCornerShape(24.dp),
    ) { Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = content) }
}

private fun patterns(value: String): JSONArray = JSONArray().also { array ->
    value.split(',').map(String::trim).filter(String::isNotEmpty).forEach(array::put)
}

@Composable
private fun DownloadScreen(
    model: AppModel,
    snapshot: JSONObject,
    prefs: android.content.SharedPreferences,
    appearance: Int,
    setAppearance: (Int) -> Unit,
    message: (String) -> Unit,
    openGallery: () -> Unit,
) {
    val activity = LocalActivity.current as ComposeActivity
    var url by rememberSaveable { mutableStateOf(prefs.getString("url", "") ?: "") }
    var allPages by rememberSaveable { mutableStateOf(prefs.getBoolean("all_pages", true)) }
    var separatePosts by rememberSaveable { mutableStateOf(prefs.getBoolean("separate_posts", false)) }
    var workers by rememberSaveable { mutableIntStateOf(prefs.getInt("workers", 2)) }
    var include by rememberSaveable { mutableStateOf(prefs.getString("include", "") ?: "") }
    var ignore by rememberSaveable { mutableStateOf(prefs.getString("ignore", "") ?: "") }
    var advanced by rememberSaveable { mutableStateOf(prefs.getBoolean("advanced_expanded", false)) }
    var themeMenu by remember { mutableStateOf(false) }
    var logs by remember { mutableStateOf(false) }
    var pendingDownloadAll by remember { mutableStateOf<String?>(null) }
    val busy = snapshot.optBoolean("busy") || model.pending
    val notificationPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }

    fun settings(): String {
        prefs.edit().putString("url", url).putBoolean("all_pages", allPages)
            .putBoolean("separate_posts", separatePosts).putInt("workers", workers)
            .putString("include", include).putString("ignore", ignore).apply()
        return JSONObject().put("url", url).put("all_pages", allPages)
            .put("separate_posts", separatePosts).put("workers", workers)
            .put("include", patterns(include)).put("ignore", patterns(ignore)).toString()
    }
    val pickDownloadDestination = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        val pendingSettings = pendingDownloadAll
        pendingDownloadAll = null
        if (uri == null) {
            if (pendingSettings != null) message("Download cancelado: nenhuma pasta foi escolhida.")
        } else if (pendingSettings != null) try {
            activity.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            model.call("set_destination", {
                activity.runService("scan") {
                    putExtra("settings", pendingSettings); putExtra("force", false); putExtra("all", true)
                }
            }, uri.toString())
        } catch (_: Exception) { message("Não foi possível usar essa pasta. Escolha outra pasta.") }
    }
    fun scan(all: Boolean) {
        if (busy || model.engine == null) { message("Aguarde a operação atual."); return }
        if (Build.VERSION.SDK_INT >= 33) notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        val currentSettings = settings()
        if (all) {
            pendingDownloadAll = currentSettings
            pickDownloadDestination.launch(null)
        } else {
            activity.runService("scan") {
                putExtra("settings", currentSettings); putExtra("force", false); putExtra("all", false)
            }
            openGallery()
        }
    }
    val pickCookies = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) model.io.execute {
            val pending = File(activity.filesDir, "cookies.pending")
            try {
                activity.contentResolver.openInputStream(uri).use { input ->
                    requireNotNull(input)
                    FileOutputStream(pending).use { output -> input.copyTo(output, 8192) }
                }
                if (pending.length() > 2 * 1024 * 1024) error("Cookies maiores que 2 MiB")
                model.call("import_cookies", { message("Cookies importados.") }, pending.absolutePath)
            } catch (error: Exception) { model.error(error); pending.delete() }
        }
    }
    val captureCookies = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        if (it.resultCode == android.app.Activity.RESULT_OK) message("Cookies salvos e prontos para uso.")
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 24.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("BUIDL", style = MaterialTheme.typography.displaySmall,
                    fontWeight = FontWeight.Normal, modifier = Modifier.weight(1f))
                Text(snapshot.optString("message", "Pronto"), style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1,
                    overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(.8f))
                Box {
                    IconButton(onClick = { themeMenu = true }) {
                        Icon(if (appearance == 2) Icons.Rounded.LightMode else Icons.Rounded.DarkMode, "Aparência")
                    }
                    DropdownMenu(themeMenu, { themeMenu = false }) {
                        listOf("Automático" to 0, "Claro" to 1, "Escuro" to 2).forEach { (label, value) ->
                            DropdownMenuItem(text = { Text(label) }, onClick = {
                                setAppearance(value); themeMenu = false
                            })
                        }
                    }
                }
            }
        }
        item {
            OutlinedTextField(
                value = url, onValueChange = { url = it }, modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("Cole o link da thread") }, singleLine = true,
                shape = RoundedCornerShape(36.dp),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                leadingIcon = { Icon(Icons.Rounded.Search, null) },
                trailingIcon = { IconButton(onClick = { advanced = !advanced }) { Icon(Icons.Rounded.MoreVert, "Mais opções") } },
            )
        }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button({ scan(false) }, Modifier.weight(1f).height(56.dp), enabled = !busy,
                    shape = RoundedCornerShape(18.dp)) {
                    Icon(Icons.Rounded.Collections, null); Spacer(Modifier.width(8.dp)); Text("Escolher")
                }
                Button({ scan(true) }, Modifier.weight(1f).height(56.dp), enabled = !busy,
                    shape = RoundedCornerShape(18.dp)) {
                    Icon(Icons.Rounded.Download, null); Spacer(Modifier.width(8.dp)); Text("Baixar tudo")
                }
            }
        }
        item {
            SectionCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Rounded.Download, null, Modifier.size(42.dp), tint = MaterialTheme.colorScheme.primary)
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Text(snapshot.optString("title").ifBlank { "Pronto para baixar" },
                            style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold,
                            maxLines = 2, overflow = TextOverflow.Ellipsis)
                        Text(if (busy) snapshot.optString("message") else "Fotos, vídeos, áudios e arquivos",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.bodyMedium)
                    }
                }
                if (busy || snapshot.optInt("total") > 0) ProgressCard(model, snapshot, { logs = true }, message)
            }
        }
        item {
            SectionCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(allPages, { allPages = it }); Text("Buscar em todas as páginas")
                }
                Text("Destino dos downloads", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text("O Android perguntará onde salvar sempre que você iniciar um download.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (snapshot.optString("destination").isNotEmpty()) {
                    Text("Última pasta usada: ${snapshot.optString("destination_label")}", style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        item {
            SectionCard {
                Text("Acesso ao fórum", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(if (snapshot.optBoolean("cookies")) "Sessão salva neste aplicativo" else "Sem sessão salva — opcional em threads públicas",
                    color = if (snapshot.optBoolean("cookies")) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                Button({ captureCookies.launch(Intent(activity, CookieCaptureActivity::class.java)) }, Modifier.fillMaxWidth(), enabled = !busy) { Text("Capturar cookies") }
                OutlinedButton({ pickCookies.launch(arrayOf("text/plain", "*/*")) }, Modifier.fillMaxWidth(), enabled = !busy) { Text("Importar cookies.txt") }
                if (snapshot.optBoolean("cookies")) TextButton({
                    model.call("remove_cookies", {
                        CookieManager.getInstance().removeAllCookies(null); CookieManager.getInstance().flush(); WebStorage.getInstance().deleteAllData()
                        message("Sessão removida.")
                    })
                }, Modifier.fillMaxWidth()) { Icon(Icons.Rounded.DeleteOutline, null); Text("Remover sessão salva") }
            }
        }
        item {
            SectionCard {
                OutlinedButton({ advanced = !advanced; prefs.edit().putBoolean("advanced_expanded", advanced).apply() }, Modifier.fillMaxWidth()) {
                    Text(if (advanced) "Ocultar opções avançadas" else "Opções avançadas")
                }
                if (advanced) {
                    Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(separatePosts, { separatePosts = it }); Text("Separar pastas por post") }
                    Text("Downloads simultâneos: $workers")
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        (1..3).forEach { FilterChip(workers == it, { workers = it }, { Text("$it") }) }
                    }
                    OutlinedTextField(include, { include = it }, Modifier.fillMaxWidth(), label = { Text("Incluir apenas") }, placeholder = { Text(".jpg, .mp4") })
                    OutlinedTextField(ignore, { ignore = it }, Modifier.fillMaxWidth(), label = { Text("Ignorar") }, placeholder = { Text(".zip") })
                }
            }
        }
        item { Text("BUIDL · 1.5.2", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelMedium) }
    }
    if (logs) LogsDialog(snapshot) { logs = false }
}

@Composable
private fun ProgressCard(model: AppModel, snapshot: JSONObject, showLogs: () -> Unit, message: (String) -> Unit) {
    val activity = LocalActivity.current as ComposeActivity
    val busy = snapshot.optBoolean("busy") || model.pending
    val total = snapshot.optInt("total")
    val done = snapshot.optInt("completed") + snapshot.optInt("skipped") + snapshot.optInt("failed")
    SectionCard {
        Text("Atividade", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(snapshot.optString("message", "Iniciando o mecanismo…"))
        if (busy || total > 0) {
            if (total > 0) LinearProgressIndicator({ done.toFloat() / total.coerceAtLeast(1) }, Modifier.fillMaxWidth())
            else LinearProgressIndicator(Modifier.fillMaxWidth())
            Text("${snapshot.optInt("completed")} concluídos  •  ${snapshot.optInt("skipped")} ignorados  •  ${snapshot.optInt("failed")} falhas",
                style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (busy) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton({ model.call("pause", null) }, Modifier.weight(1f)) { Icon(Icons.Rounded.Pause, null); Text(if (snapshot.optString("state") == "paused") "Continuar" else "Pausar") }
            OutlinedButton({ activity.runService("cancel") }, Modifier.weight(1f)) { Icon(Icons.Rounded.Stop, null); Text("Parar") }
        }
        TextButton(showLogs, Modifier.fillMaxWidth()) { Text("Ver falhas e atividade") }
        val error = snapshot.optString("error_message")
        LaunchedEffect(snapshot.optLong("ui_error")) { if (error.isNotBlank()) message(error) }
    }
}

private fun parseMedia(text: String): List<MediaItem> {
    val array = runCatching { JSONArray(text) }.getOrDefault(JSONArray())
    return (0 until array.length()).mapNotNull { index -> array.optJSONObject(index)?.let { item ->
        MediaItem(index, item.optString("name"), item.optString("kind"), item.optString("post"), item.optString("host"), item.optString("origin"))
    } }
}

@Composable
private fun GalleryScreen(model: AppModel, snapshot: JSONObject, media: List<MediaItem>, message: (String) -> Unit) {
    val activity = LocalActivity.current as ComposeActivity
    var query by rememberSaveable { mutableStateOf(model.query) }
    var kind by rememberSaveable { mutableStateOf(model.kind) }
    var pendingIndices by remember { mutableStateOf<String?>(null) }
    val selected = remember { mutableStateMapOf<Int, Boolean>() }
    var queue by remember { mutableIntStateOf(snapshot.optInt("queue_id")) }
    if (queue != snapshot.optInt("queue_id")) { queue = snapshot.optInt("queue_id"); selected.clear(); model.selected.clear() }
    val kinds = listOf("Todos", "Imagens", "Vídeos", "Áudios", "Arquivos")
    val filtered = media.filter { item ->
        (kind == "Todos" || item.kind == kind) && listOf(item.name, item.host, item.post).joinToString(" ").lowercase(Locale.ROOT).contains(query.lowercase(Locale.ROOT))
    }
    val pickDownloadDestination = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        val ids = pendingIndices
        pendingIndices = null
        if (uri == null) {
            if (ids != null) message("Download cancelado: nenhuma pasta foi escolhida.")
        } else if (ids != null) try {
            activity.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            model.call("set_destination", {
                activity.runService("download") {
                    putExtra("queue", snapshot.optInt("queue_id")); putExtra("indices", ids)
                }
            }, uri.toString())
        } catch (_: Exception) { message("Não foi possível usar essa pasta. Escolha outra pasta.") }
    }
    fun download(indices: List<Int>) {
        if (indices.isEmpty()) { message("Nenhum arquivo corresponde ao filtro."); return }
        pendingIndices = JSONArray(indices).toString()
        pickDownloadDestination.launch(null)
    }
    Column(Modifier.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        ScreenTitle("Downloads", if (media.isEmpty()) "Analise uma thread para criar a lista." else "${filtered.size} itens · ${snapshot.optString("title")}")
        if (media.isEmpty()) {
            SectionCard { Text("Nenhum conteúdo analisado ainda.", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        } else {
            OutlinedTextField(query, { query = it; model.query = it }, Modifier.fillMaxWidth(), label = { Text("Buscar na galeria") },
                leadingIcon = { Icon(Icons.Rounded.Search, null) }, singleLine = true, shape = RoundedCornerShape(32.dp))
            LazyRow(modifier = Modifier.fillMaxWidth().height(52.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(kinds) { value -> FilterChip(kind == value, { kind = value; model.kind = value }, { Text(value) }) }
            }
            Text("${selected.count { it.value }} selecionados  •  ${filtered.size} resultados", color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button({ download(filtered.map { it.index }) }, Modifier.weight(1f).height(54.dp), enabled = filtered.isNotEmpty() && !snapshot.optBoolean("busy"), shape = RoundedCornerShape(18.dp)) { Icon(Icons.Rounded.Download, null); Spacer(Modifier.width(6.dp)); Text("Baixar filtro (${filtered.size})") }
                OutlinedButton({ download(selected.filterValues { it }.keys.toList()) }, Modifier.weight(1f), enabled = selected.any { it.value }) { Text("Selecionados (${selected.count { it.value }})") }
            }
            LazyVerticalGrid(
                columns = GridCells.Adaptive(360.dp), modifier = Modifier.weight(1f).fillMaxWidth(),
                contentPadding = PaddingValues(bottom = 20.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                items(filtered, key = { it.index }) { item ->
                    MediaCard(model, snapshot.optInt("queue_id"), item, selected[item.index] == true,
                        { checked -> selected[item.index] = checked; if (checked) model.selected.add(item.index) else model.selected.remove(item.index) }, message)
                }
            }
        }
    }
}

@Composable
private fun MediaCard(model: AppModel, queue: Int, item: MediaItem, checked: Boolean, setChecked: (Boolean) -> Unit, message: (String) -> Unit) {
    val activity = LocalActivity.current as ComposeActivity
    var video by remember { mutableStateOf(false) }
    val bitmap by produceState<Bitmap?>(null, queue, item.index) {
        val key = "$queue:${item.index}"
        value = model.thumbnails.get(key) ?: withContext(Dispatchers.IO) {
            runCatching {
                val bytes = model.engine?.callAttr("thumbnail", queue, item.index)?.toJava(ByteArray::class.java)
                bytes?.let { BitmapFactory.decodeByteArray(it, 0, it.size) }?.also { model.thumbnails.put(key, it) }
            }.getOrNull()
        }
    }
    Card(shape = RoundedCornerShape(22.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer),
        modifier = Modifier.fillMaxWidth().clickable { setChecked(!checked) }) {
        Column(Modifier.fillMaxWidth()) {
            Box(Modifier.fillMaxWidth().height(178.dp).background(MaterialTheme.colorScheme.surfaceContainerHighest), Alignment.Center) {
                if (bitmap != null) Image(bitmap!!.asImageBitmap(), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                else Icon(Icons.Rounded.Collections, "Sem miniatura", Modifier.size(44.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                Surface(Modifier.align(Alignment.TopStart).padding(10.dp), shape = RoundedCornerShape(14.dp),
                    color = MaterialTheme.colorScheme.surface.copy(alpha = .88f)) { Checkbox(checked, setChecked) }
                Surface(Modifier.align(Alignment.BottomEnd).padding(12.dp), shape = RoundedCornerShape(16.dp),
                    color = MaterialTheme.colorScheme.primaryContainer) {
                    Text(item.kind, Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
                        color = MaterialTheme.colorScheme.onPrimaryContainer, fontWeight = FontWeight.Bold)
                }
            }
            Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                Text(item.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text("${item.post}  •  ${item.host}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    if (item.kind == "Vídeos") TextButton({ video = true }) { Icon(Icons.Rounded.PlayArrow, null); Text("Prévia") }
                    TextButton({
                        val uri = Uri.parse(item.origin)
                        if (uri.scheme == "http" || uri.scheme == "https") runCatching { activity.startActivity(Intent(Intent.ACTION_VIEW, uri)) }.onFailure { message("Não há navegador disponível.") }
                    }) { Icon(Icons.AutoMirrored.Rounded.OpenInNew, null); Text("Origem") }
                }
            }
        }
    }
    if (video) VideoDialog(model, queue, item.index) { video = false }
}

@Composable
private fun VideoDialog(model: AppModel, queue: Int, index: Int, close: () -> Unit) {
    var source by remember { mutableStateOf<Pair<Uri, Map<String, String>>?>(null) }
    var failed by remember { mutableStateOf(false) }
    LaunchedEffect(queue, index) {
        source = withContext(Dispatchers.IO) { runCatching {
            val result = JSONObject(model.engine.callAttr("video_source", queue, index).toString())
            val headers = mutableMapOf<String, String>(); val json = result.getJSONObject("headers")
            json.keys().forEach { headers[it] = json.getString(it) }
            Uri.parse(result.getString("url")) to headers
        }.onFailure { failed = true }.getOrNull() }
    }
    AlertDialog(onDismissRequest = close, confirmButton = { TextButton(close) { Text("Voltar") } }, title = { Text("Prévia do vídeo") }, text = {
        if (failed) Text("Prévia indisponível neste host. O arquivo ainda pode ser baixado.")
        else if (source == null) LinearProgressIndicator(Modifier.fillMaxWidth())
        else AndroidView(factory = { context -> VideoView(context).apply { setVideoURI(source!!.first, source!!.second); setOnPreparedListener { it.setVolume(0f, 0f); start() }; setOnErrorListener { _, _, _ -> failed = true; true } } }, Modifier.fillMaxWidth().height(260.dp))
    })
}

@Composable
private fun FilesScreen(model: AppModel, snapshot: JSONObject, message: (String) -> Unit, chooseThread: () -> Unit) {
    val activity = LocalActivity.current as ComposeActivity
    var refresh by remember { mutableIntStateOf(0) }
    val files = remember { mutableStateListOf<JSONObject>() }
    var loading by remember { mutableStateOf(true) }
    LaunchedEffect(refresh, snapshot.optString("destination")) {
        loading = true
        model.call("files", { result -> files.clear(); val array = JSONArray(result.toString()); (0 until array.length()).forEach { files.add(array.getJSONObject(it)) }; loading = false })
    }
    val export = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) model.io.execute {
            val outcome = runCatching {
                val listing = JSONArray(model.engine.callAttr("files").toString())
                val copied = ExportFiles.copy(activity, model.downloads, uri, listing) { _, _ -> }
                "$copied arquivos exportados. Os originais foram mantidos."
            }.getOrElse { "Não foi possível exportar: ${it.message}" }
            activity.runOnUiThread { message(outcome) }
        }
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { ScreenTitle("Seus arquivos", snapshot.optString("destination_label", "Escolha uma pasta ao baixar")) }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button({ export.launch(null) }, Modifier.weight(1f), enabled = !snapshot.optBoolean("busy")) { Icon(Icons.Rounded.Folder, null); Text("Exportar") }
                OutlinedButton({ refresh++ }, Modifier.weight(1f)) { Icon(Icons.Rounded.Refresh, null); Text("Atualizar") }
            }
        }
        if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
        if (!loading && files.isEmpty()) item { SectionCard { Text("Ainda não há downloads nesta pasta."); Button(chooseThread) { Text("Escolher uma thread") } } }
        items(files.take(150), key = { it.optString("path", it.optString("uri")) }) { file ->
            SectionCard {
                Text(file.optString("name"), fontWeight = FontWeight.SemiBold)
                Text("${file.optString("relative")} • ${android.text.format.Formatter.formatFileSize(activity, file.optLong("size"))}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedButton({ openFile(activity, file, message) }, Modifier.fillMaxWidth()) { Icon(Icons.AutoMirrored.Rounded.OpenInNew, null); Text("Abrir / visualizar") }
            }
        }
    }
}

private fun openFile(activity: ComposeActivity, file: JSONObject, message: (String) -> Unit) {
    runCatching {
        val uri = if (file.has("uri")) Uri.parse(file.getString("uri")) else FileProvider.getUriForFile(activity, activity.packageName + ".files", File(file.getString("path")))
        activity.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(uri, file.optString("mime", "*/*")).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION))
    }.onFailure { message("Não há aplicativo compatível para abrir este arquivo.") }
}

@Composable
private fun LogsDialog(snapshot: JSONObject, close: () -> Unit) {
    val errors = snapshot.optJSONArray("errors") ?: JSONArray()
    val logs = snapshot.optJSONArray("logs") ?: JSONArray()
    val text = buildString {
        if (errors.length() > 0) { append("FALHAS / AVISOS\n\n"); (0 until errors.length()).forEach { append(errors.optString(it)).append("\n\n") } }
        append("ATIVIDADE\n\n"); (0 until logs.length()).forEach { append(logs.optString(it)).append("\n\n") }
    }
    AlertDialog(onDismissRequest = close, confirmButton = { TextButton(close) { Text("Fechar") } }, title = { Text("Atividade do BUIDL") }, text = {
        Text(text.ifBlank { "Nenhuma atividade registrada." }, Modifier.verticalScroll(rememberScrollState()))
    })
}
