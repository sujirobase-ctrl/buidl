package com.sujirobase.buidl;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.provider.DocumentsContract;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.widget.*;
import androidx.core.content.FileProvider;
import androidx.core.view.ViewCompat;
import com.chaquo.python.PyObject;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;

public class MainActivity extends Activity {
    private int BG, CARD, ACCENT, TEXT, MUTED;
    private Ui ui;
    private boolean wide, inlineProgress, largeText;
    private final List<Button> tabButtons=new ArrayList<>();
    private Button appFolderButton, removeCookiesButton;
    private static final int PAGE_SIZE = 12, PICK_COOKIES = 10, PICK_EXPORT = 11, CAPTURE_COOKIES = 12, PICK_DESTINATION = 13;
    private AppModel model;
    private SharedPreferences prefs;
    private LinearLayout root, content, progressCard, progressActions;
    private TextView status, counts, cookieLabel, galleryCount, destinationLabel, activityHeading;
    private Button activityLogButton;
    private String spokenState="";
    private ProgressBar progress;
    private EditText url, include, ignore, search;
    private CheckBox allPages, separatePosts;
    private Spinner workers;
    private Button scanButton, allButton, pauseButton, stopButton, selectionButton;
    private LinearLayout galleryList;
    private int tab = 0, shownQueue = -1, galleryGeneration = 0;
    private long lastUiError = 0;
    private boolean destroyed = false;
    private boolean openGalleryWhenReady = false;
    private AlertDialog activeVideoDialog;
    private final Handler handler = new Handler();
    private final List<View> formControls = new ArrayList<>();
    private final Runnable poll = new Runnable() {
        @Override public void run() { if (!destroyed) { updateStatus(); handler.postDelayed(this, 500); } }
    };

    @Override public void onCreate(Bundle savedInstanceState) {
        Ui.applyTheme(this);
        super.onCreate(savedInstanceState);
        ui=new Ui(this);ui.window(this);BG=ui.bg;CARD=ui.surface;ACCENT=ui.accent;TEXT=ui.text;MUTED=ui.muted;
        model = ((BuidlApplication)getApplication()).model;
        prefs = getSharedPreferences("buidl", MODE_PRIVATE);
        largeText=getResources().getConfiguration().fontScale>=1.3f;
        wide=getResources().getConfiguration().screenWidthDp>=640 && !largeText;
        inlineProgress=!wide && (largeText || getResources().getConfiguration().screenHeightDp<580);
        root = column(); root.setBackgroundColor(BG);
        root.setPadding(dp(16), dp(8), dp(16), dp(8));
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(dp(16) + insets.getSystemWindowInsetLeft(), dp(8) + insets.getSystemWindowInsetTop(),
                    dp(16) + insets.getSystemWindowInsetRight(), dp(8) + insets.getSystemWindowInsetBottom());
            return insets;
        });
        setContentView(root);
        LinearLayout brand = row();
        ImageView symbol=new ImageView(this);symbol.setImageDrawable(ui.icon("download",ui.onAccent));symbol.setPadding(dp(8),dp(8),dp(8),dp(8));symbol.setBackground(ui.shape(ACCENT,12,0,0));symbol.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        LinearLayout.LayoutParams mark=new LinearLayout.LayoutParams(dp(38),dp(38));mark.setMargins(0,0,dp(10),0);brand.addView(symbol,mark);
        TextView logo = text("BUIDL",22,TEXT); logo.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));logo.setLetterSpacing(0.06f);
        brand.addView(logo, new LinearLayout.LayoutParams(0, -2, 1));
        Button appearance=button("",false,this::showAppearance);Ui.key(appearance,"aparencia");appearance.setContentDescription("Aparência. Escolher tema claro, escuro ou automático");
        appearance.setCompoundDrawablesWithIntrinsicBounds(ui.icon("palette",TEXT),null,null,null);brand.addView(appearance,new LinearLayout.LayoutParams(dp(52),dp(52)));root.addView(brand);
        LinearLayout tabs = row(); tabs.setPadding(0, dp(8), 0, dp(8));
        String[] labels = {"Baixar", "Galeria", "Arquivos"};
        for (int i=0; i<labels.length; i++) { final int index=i;
            Button button = button(labels[i], false, () -> showTab(index));
            button.setPadding(dp(6),dp(8),dp(6),dp(8));button.setTextSize(14);tabButtons.add(button);
            tabs.addView(button, weighted());
        }
        if(wide)root.addView(tabs);
        ScrollView scroll = new ScrollView(this); scroll.setFillViewport(true);
        content = column(); scroll.addView(content);
        LinearLayout body = wide ? row() : column(); body.setGravity(Gravity.TOP);
        root.addView(body, new LinearLayout.LayoutParams(-1, 0, 1));
        body.addView(scroll, wide ? new LinearLayout.LayoutParams(0, -1, 1) : new LinearLayout.LayoutParams(-1, 0, 1));
        progressCard = card();
        activityHeading=ui.heading("Atividade",16);progressCard.addView(activityHeading);
        status = text("Iniciando o Python…",15,TEXT);Ui.key(status,"status_download");status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        progressCard.addView(status);
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setProgressTintList(ColorStateList.valueOf(ACCENT));
        progressCard.addView(progress, new LinearLayout.LayoutParams(-1, dp(12)));
        counts = text("", 11, MUTED); progressCard.addView(counts);
        selectionButton = button("Baixar selecionados", true, () -> download(false));
        Ui.key(selectionButton,"baixar_selecionados"); progressCard.addView(selectionButton);
        LinearLayout actions = largeText ? column() : row();
        progressActions = actions;
        pauseButton = button("Pausar fila", false, () -> model.call("pause", null));
        stopButton = button("Parar fila", false, () -> model.call("cancel", null));
        actions.addView(pauseButton,largeText ? new LinearLayout.LayoutParams(-1,-2) : weighted()); actions.addView(stopButton,largeText ? new LinearLayout.LayoutParams(-1,-2) : weighted());
        progressCard.addView(actions);
        activityLogButton=button("Ver falhas e atividade",false,this::showLogs);progressCard.addView(activityLogButton);
        if (wide) {
            ScrollView sideScroll=new ScrollView(this);sideScroll.addView(progressCard);
            LinearLayout.LayoutParams side = new LinearLayout.LayoutParams(dp(214), -1); side.setMargins(dp(16),0,0,0);body.addView(sideScroll,side);
        } else if(!inlineProgress)body.addView(progressCard);
        if(!wide)root.addView(tabs);
        shownQueue=model.snapshot.optInt("queue_id");
        showTab(savedInstanceState == null ? 0 : savedInstanceState.getInt("tab", 0));
        handler.post(poll);
    }

    @Override protected void onSaveInstanceState(Bundle out) { saveForm(); out.putInt("tab", tab); super.onSaveInstanceState(out); }
    @Override protected void onPause() { saveForm(); super.onPause(); }
    @Override protected void onDestroy() { destroyed=true; if(activeVideoDialog!=null)activeVideoDialog.dismiss(); galleryGeneration++; handler.removeCallbacks(poll); super.onDestroy(); }

    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }
    private LinearLayout column() { LinearLayout l=new LinearLayout(this); l.setOrientation(LinearLayout.VERTICAL); return l; }
    private LinearLayout row() { LinearLayout l=new LinearLayout(this); l.setGravity(Gravity.CENTER_VERTICAL); return l; }
    private LinearLayout.LayoutParams weighted() { LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-2,1); p.setMargins(dp(2),0,dp(2),0); return p; }
    private GradientDrawable background(int color) { return ui.shape(color,18,0,0); }
    private LinearLayout card() { LinearLayout l=column();l.setPadding(dp(16),dp(14),dp(16),dp(14));l.setBackground(background(CARD));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(8),0,dp(8));l.setLayoutParams(p);return l; }
    private TextView text(String value,int size,int color) { return ui.text(value,size,color); }
    private Button button(String label,boolean primary,Runnable action) { return ui.button(label,primary,action); }
    private EditText field(String hint,String value) { return ui.field(hint,value); }
    private CheckBox checkbox(String label,boolean checked) { return ui.checkbox(label,checked); }
    private void showAppearance() {
        new AlertDialog.Builder(this).setTitle("Aparência").setSingleChoiceItems(new String[]{"Automático (sistema)","Claro","Escuro"},prefs.getInt("appearance",2),(dialog,which) -> {
            saveForm();prefs.edit().putInt("appearance",which).apply();dialog.dismiss();recreate();
        }).setNegativeButton("Voltar",null).show();
    }
    private void section(LinearLayout parent,String title,String icon) {
        TextView heading=ui.heading(title,17);heading.setCompoundDrawablesWithIntrinsicBounds(ui.icon(icon,ACCENT),null,null,null);heading.setCompoundDrawablePadding(dp(10));parent.addView(heading);
    }
    private void setText(TextView view,String value) { if(!value.contentEquals(view.getText()))view.setText(value); }

    private void showTab(int next) {
        saveForm(); tab=next; galleryGeneration++; formControls.clear();
        url=null; scanButton=null; allButton=null; cookieLabel=null; destinationLabel=null;appFolderButton=null;removeCookiesButton=null;
        content.removeAllViews();
        if(inlineProgress)content.addView(progressCard);
        if (tab==0) showDownload(); else if (tab==1) showGallery(); else showFiles();
        String[] icons={"download","grid","folder"};
        for(int i=0;i<tabButtons.size();i++) {Button b=tabButtons.get(i);boolean selected=i==tab;ui.styleButton(b,selected);b.setPadding(dp(6),dp(8),dp(6),dp(8));b.setTextSize(14);b.setSelected(selected);
            ViewCompat.setStateDescription(b,selected ? "Aba atual" : null);
            b.setCompoundDrawablesWithIntrinsicBounds(null,largeText ? null : ui.icon(icons[i],selected ? ui.onAccent : MUTED),null,null);b.setCompoundDrawablePadding(dp(4));}
        content.setFocusableInTouchMode(true); content.requestFocus();
        content.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        updateStatus();
    }

    private void showDownload() {
        content.addView(ui.heading("Sua próxima coleção",26));
        content.addView(text("Cole uma thread. Escolha o que vale guardar.",14,MUTED));
        LinearLayout form=card();
        url=field("https://simpcity.cr/threads/…",prefs.getString("url","")); Ui.key(url,"url_thread");
        url.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);
        form.addView(ui.label("Link da thread",url)); form.addView(url);
        allPages=checkbox("Buscar em todas as páginas",prefs.getBoolean("all_pages",true)); form.addView(allPages);
        scanButton=button("Analisar e escolher",true,() -> startScan(false,false)); Ui.key(scanButton,"analisar_thread");
        scanButton.setCompoundDrawablesWithIntrinsicBounds(ui.icon("search",ui.onAccent),null,null,null);form.addView(scanButton);
        allButton=button("Baixar tudo",false,() -> startScan(false,true));form.addView(allButton);
        content.addView(form);

        LinearLayout destinationCard=card(); section(destinationCard,"Pasta de destino","folder");
        destinationLabel=text("",15,TEXT); Ui.key(destinationLabel,"pasta_destino"); destinationCard.addView(destinationLabel);
        Button chooseFolder=button("Escolher pasta de destino",false,() -> {
            if(model.pending || model.engine==null || model.snapshot.optBoolean("busy")) { message("Aguarde a operação atual."); return; }
            Intent pick=new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
            String previous=model.snapshot.optString("destination");
            if(android.os.Build.VERSION.SDK_INT>=26 && !previous.isEmpty())pick.putExtra(DocumentsContract.EXTRA_INITIAL_URI,Uri.parse(previous));
            startActivityForResult(pick,PICK_DESTINATION);
        }); Ui.key(chooseFolder,"escolher_pasta_destino"); destinationCard.addView(chooseFolder); formControls.add(chooseFolder);
        appFolderButton=button("Usar pasta do aplicativo",false,() -> {
            if(model.pending || model.snapshot.optBoolean("busy")) { message("Aguarde a operação atual."); return; }
            model.call("set_destination",unused -> updateStatus(),"");
        }); Ui.key(appFolderButton,"usar_pasta_app"); destinationCard.addView(appFolderButton); formControls.add(appFolderButton);
        destinationCard.addView(text("Sua escolha é lembrada. Arquivos anteriores não são movidos.",14,MUTED));
        content.addView(destinationCard);
        LinearLayout cookies=card(); section(cookies,"Acesso ao fórum","shield");
        cookieLabel=text("",14,MUTED); cookies.addView(cookieLabel);
        Button capture=button("Capturar cookies",false,() -> {
            if(model.pending || model.engine==null || model.snapshot.optBoolean("busy")) { message("Aguarde a operação atual."); return; }
            startActivityForResult(new Intent(this,CookieCaptureActivity.class),CAPTURE_COOKIES);
        });
        Ui.key(capture,"capturar_cookies"); cookies.addView(capture); formControls.add(capture);
        cookies.addView(text("Entre no SimpCity dentro do app e toque em Pronto.",14,MUTED));
        LinearLayout cookieActions=column();
        Button importButton=button("Importar cookies.txt",false,() -> {
            if (model.snapshot.optBoolean("busy")) { message("Aguarde a operação terminar."); return; }
            Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);
            startActivityForResult(intent,PICK_COOKIES);
        });
        removeCookiesButton=button("Remover sessão salva",false,() -> new AlertDialog.Builder(this).setMessage("Remover os cookies salvos e sair do navegador interno do BUIDL? Outros navegadores não serão alterados.")
                .setPositiveButton("Remover",(d,w) -> model.call("remove_cookies",r -> {
                    android.webkit.CookieManager.getInstance().removeAllCookies(removed -> {
                        android.webkit.CookieManager.getInstance().flush();
                        android.webkit.WebStorage.getInstance().deleteAllData();
                        message("Cookies e sessão do navegador interno removidos.");
                    });
                })).setNegativeButton("Voltar",null).show());
        cookieActions.addView(importButton); cookieActions.addView(removeCookiesButton); cookies.addView(cookieActions);
        formControls.add(importButton);formControls.add(removeCookiesButton);
        content.addView(cookies);

        LinearLayout advanced=card(), options=column();
        separatePosts=checkbox("Separar pastas por post",prefs.getBoolean("separate_posts",false));options.addView(separatePosts);
        workers=new Spinner(this);Ui.key(workers,"downloads_simultaneos");ui.spinner(workers,new String[]{"1 arquivo por vez","2 arquivos por vez","3 arquivos por vez"});
        workers.setSelection(Math.max(0,Math.min(2,prefs.getInt("workers",2)-1)));options.addView(ui.label("Downloads simultâneos",workers));options.addView(workers);
        include=field("Ex.: .jpg, .mp4",prefs.getString("include",""));Ui.key(include,"incluir_arquivos");
        ignore=field("Ex.: .zip",prefs.getString("ignore",""));Ui.key(ignore,"ignorar_arquivos");
        options.addView(ui.label("Incluir apenas (opcional)",include));options.addView(include);
        options.addView(ui.label("Ignorar (opcional)",ignore));options.addView(ignore);
        options.addView(text("Separe os filtros por vírgula. Deixe vazio para aceitar todos.",14,MUTED));
        boolean expanded=prefs.getBoolean("advanced_expanded",false);options.setVisibility(expanded ? View.VISIBLE : View.GONE);
        Button toggle=button(expanded ? "Ocultar opções avançadas" : "Opções avançadas",false,() -> {});Ui.key(toggle,"opcoes_avancadas");
        ViewCompat.setStateDescription(toggle,expanded ? "Expandido" : "Recolhido");
        toggle.setOnClickListener(v -> {boolean show=options.getVisibility()!=View.VISIBLE;options.setVisibility(show ? View.VISIBLE : View.GONE);
            toggle.setText(show ? "Ocultar opções avançadas" : "Opções avançadas");ViewCompat.setStateDescription(toggle,show ? "Expandido" : "Recolhido");prefs.edit().putBoolean("advanced_expanded",show).apply();});
        advanced.addView(toggle);advanced.addView(options);content.addView(advanced);
        formControls.add(url);formControls.add(allPages);formControls.add(separatePosts);formControls.add(workers);formControls.add(include);formControls.add(ignore);
        content.addView(button("Ver falhas e atividade",false,this::showLogs));
        content.addView(text("BUIDL · 2.0.0\nNa pasta do app, exporte antes de desinstalar. Uma pasta externa precisa de espaço temporário durante o download.",14,MUTED));
    }

    private void saveForm() {
        if (url==null) return;
        prefs.edit().putString("url",url.getText().toString()).putBoolean("all_pages",allPages.isChecked())
                .putBoolean("separate_posts",separatePosts.isChecked()).putInt("workers",workers.getSelectedItemPosition()+1)
                .putString("include",include.getText().toString()).putString("ignore",ignore.getText().toString()).apply();
    }
    private JSONArray patterns(String value) { JSONArray out=new JSONArray(); for(String s:value.split(",")) if(!s.trim().isEmpty()) out.put(s.trim()); return out; }
    private String settings() {
        saveForm(); JSONObject o=new JSONObject();
        try { o.put("url",prefs.getString("url","")); o.put("all_pages",prefs.getBoolean("all_pages",true));
            o.put("separate_posts",prefs.getBoolean("separate_posts",false)); o.put("workers",prefs.getInt("workers",2));
            o.put("include",patterns(prefs.getString("include",""))); o.put("ignore",patterns(prefs.getString("ignore","")));
        } catch(Exception ignored) { } return o.toString();
    }
    private void startServiceAction(Intent intent) {
        if(model.pending || model.snapshot.optBoolean("busy")) { message("Aguarde a operação atual."); return; }
        if(android.os.Build.VERSION.SDK_INT>=33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},20);
        if(android.os.Build.VERSION.SDK_INT>=26) startForegroundService(intent); else startService(intent);
    }
    private void startScan(boolean force,boolean all) {
        if (!model.pending && !model.snapshot.optBoolean("busy")) openGalleryWhenReady = !all;
        startServiceAction(new Intent(this,DownloadService.class).setAction("scan").putExtra("settings",settings()).putExtra("force",force).putExtra("all",all));
    }
    private void download(boolean all) {
        if(!all && model.selected.isEmpty()) { message("Marque pelo menos um arquivo."); return; }
        JSONArray ids=new JSONArray(); for(int index:model.selected) ids.put(index);
        startServiceAction(new Intent(this,DownloadService.class).setAction("download").putExtra("queue",model.snapshot.optInt("queue_id"))
                .putExtra("indices",all ? "null" : ids.toString()));
    }

    private void updateStatus() {
        JSONObject s=model.snapshot; boolean busy=s.optBoolean("busy") || model.pending;
        boolean selecting=tab==1 && model.items.length()>0;
        selectionButton.setVisibility(selecting ? View.VISIBLE : View.GONE);
        String state=s.optString("state");
        status.setAccessibilityLiveRegion(state.equals(spokenState) ? View.ACCESSIBILITY_LIVE_REGION_NONE : View.ACCESSIBILITY_LIVE_REGION_POLITE);spokenState=state;
        setText(status,s.optString("message","Iniciando o Python…"));
        int done=s.optInt("completed")+s.optInt("skipped")+s.optInt("failed"), total=s.optInt("total");
        progress.setIndeterminate(busy && total==0); progress.setMax(Math.max(total,1)); progress.setProgress(done);
        progress.setContentDescription("Progresso: "+done+" de "+total+" arquivos");
        setText(counts,s.optInt("completed")+" concluídos  •  "+s.optInt("skipped")+" ignorados  •  "+s.optInt("failed")+" falhas");
        status.setTextColor(s.optInt("failed")>0 || state.equals("error") ? ui.error : TEXT);
        boolean activity=busy || total>0 || state.equals("error") || state.equals("failed");
        boolean expandedActivity=wide || busy;
        progressCard.setVisibility(wide || activity || selecting ? View.VISIBLE : View.GONE);
        for(View v:new View[]{activityHeading,status})v.setVisibility(expandedActivity ? View.VISIBLE : View.GONE);
        activityLogButton.setVisibility(wide || activity ? View.VISIBLE : View.GONE);
        String summary=s.optInt("completed")+" concluídos · "+s.optInt("failed")+" falhas";
        setText(activityLogButton,expandedActivity ? "Ver falhas e atividade" : (total>0 ? summary : s.optString("message","Atividade"))+"\nVer atividade");
        activityLogButton.setContentDescription((expandedActivity ? "" : s.optString("message")+". "+counts.getText()+". ")+"Ver falhas e atividade");
        activityLogButton.setTextColor(s.optInt("failed")>0 ? ui.error : TEXT);
        progress.setVisibility(expandedActivity && (busy || total>0) ? View.VISIBLE : View.GONE);counts.setVisibility(expandedActivity && total>0 ? View.VISIBLE : View.GONE);
        progressActions.setVisibility(busy ? View.VISIBLE : View.GONE);
        pauseButton.setEnabled(state.equals("downloading")||state.equals("paused"));
        setText(pauseButton,state.equals("paused") ? "Continuar fila" : "Pausar fila"); stopButton.setEnabled(busy);
        if(scanButton!=null) { scanButton.setEnabled(!busy && model.engine!=null); allButton.setEnabled(!busy && model.engine!=null); }
        if(selectionButton!=null) selectionButton.setEnabled(!busy && !model.selected.isEmpty());
        for(View v:formControls) v.setEnabled(!busy && model.engine!=null);
        if(cookieLabel!=null) {setText(cookieLabel,s.optBoolean("cookies") ? "Sessão salva · apenas neste aplicativo" : "Sem sessão salva. Opcional em threads públicas.");cookieLabel.setTextColor(s.optBoolean("cookies") ? ui.success : MUTED);}
        if(destinationLabel!=null) setText(destinationLabel,s.optString("destination_label","Pasta do aplicativo"));
        if(appFolderButton!=null)appFolderButton.setVisibility(s.optString("destination").isEmpty() ? View.GONE : View.VISIBLE);
        if(removeCookiesButton!=null)removeCookiesButton.setVisibility(s.optBoolean("cookies") ? View.VISIBLE : View.GONE);
        int queue=s.optInt("queue_id");
        if (model.selectionQueue != queue) { model.selected.clear(); model.page=0; model.selectionQueue=queue; }
        if(shownQueue!=queue) {
            shownQueue=queue;
            if(tab==1) showTab(1);
            else if(queue>0 && state.equals("ready")) showTab(1);
        }
        if (openGalleryWhenReady && state.equals("ready") && !busy) { openGalleryWhenReady=false; if(tab!=1)showTab(1); }
        long uiError=s.optLong("ui_error"); if(uiError>lastUiError) { lastUiError=uiError; message(s.optString("error_message",s.optString("message"))); }
    }

    private void showGallery() {
        content.addView(ui.heading("Sua galeria",26));
        if(model.items.length()==0) { LinearLayout empty=card();section(empty,"Uma coleção à sua escolha","grid");empty.addView(text("Analise uma thread para ver as prévias e selecionar os arquivos. A galeria fica guardada ao trocar de aba.",15,MUTED));empty.addView(button("Escolher uma thread",true,() -> showTab(0)));content.addView(empty);return; }
        content.addView(text(model.snapshot.optString("title"),14,MUTED));
        LinearLayout filters=card();
        search=field("Nome, host ou post",model.query);Ui.key(search,"busca_galeria");filters.addView(ui.label("Buscar na galeria",search));filters.addView(search);
        Spinner type=new Spinner(this); String[] kinds={"Todos","Imagens","Vídeos","Áudios","Arquivos"};
        Ui.key(type,"tipo_arquivo");ui.spinner(type,kinds);
        type.setSelection(Math.max(0,java.util.Arrays.asList(kinds).indexOf(model.kind)));filters.addView(ui.label("Tipo de arquivo",type));filters.addView(type);
        boolean filtering=prefs.getBoolean("gallery_filters_expanded",false) || !model.query.isEmpty() || !model.kind.equals("Todos");
        filters.setVisibility(filtering ? View.VISIBLE : View.GONE);
        Button filterToggle=button(filtering ? "Ocultar busca e filtros" : "Buscar e filtrar",false,() -> {});
        filterToggle.setCompoundDrawablesWithIntrinsicBounds(ui.icon("search",TEXT),null,null,null);ViewCompat.setStateDescription(filterToggle,filtering ? "Expandido" : "Recolhido");
        filterToggle.setOnClickListener(v -> {boolean show=filters.getVisibility()!=View.VISIBLE;filters.setVisibility(show ? View.VISIBLE : View.GONE);filterToggle.setText(show ? "Ocultar busca e filtros" : "Buscar e filtrar");ViewCompat.setStateDescription(filterToggle,show ? "Expandido" : "Recolhido");prefs.edit().putBoolean("gallery_filters_expanded",show).apply();});
        content.addView(filterToggle);content.addView(filters);
        galleryCount=text("",14,ACCENT);
        LinearLayout selection=largeText ? column() : row();
        selection.addView(galleryCount,largeText ? new LinearLayout.LayoutParams(-1,-2) : new LinearLayout.LayoutParams(0,-2,1));
        Button options=button("Opções",false,() -> {}); Ui.key(options,"galeria_opcoes");options.setContentDescription("Opções de seleção e atualização da galeria");
        options.setOnClickListener(v -> {
            PopupMenu menu=new PopupMenu(this,options);
            for(String name:new String[]{"Marcar filtro","Desmarcar filtro","Baixar todos","Atualizar thread"})menu.getMenu().add(name);
            menu.setOnMenuItemClickListener(item -> { String name=item.getTitle().toString();
                if(name.equals("Marcar filtro")){for(int i:filtered())model.selected.add(i);renderGallery();}
                if(name.equals("Desmarcar filtro")){for(int i:filtered())model.selected.remove(i);renderGallery();}
                if(name.equals("Baixar todos"))download(true);
                if(name.equals("Atualizar thread"))startScan(true,false);
                return true;
            });menu.show();
        });selection.addView(options,largeText ? new LinearLayout.LayoutParams(-1,-2) : new LinearLayout.LayoutParams(-2,-2));content.addView(selection);
        galleryList=column(); content.addView(galleryList);
        renderGallery();
        search.addTextChangedListener(new TextWatcher(){ public void beforeTextChanged(CharSequence s,int a,int c,int f){} public void onTextChanged(CharSequence s,int a,int b,int c){ model.query=s.toString(); model.page=0; renderGallery(); } public void afterTextChanged(Editable e){} });
        type.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){
            public void onItemSelected(AdapterView<?> p,View v,int pos,long id){ if(!model.kind.equals(kinds[pos])) { model.kind=kinds[pos]; model.page=0; renderGallery(); } }
            public void onNothingSelected(AdapterView<?> p){} });
    }
    private List<Integer> filtered() {
        List<Integer> result=new ArrayList<>(); String query=model.query.toLowerCase(Locale.ROOT);
        for(int i=0;i<model.items.length();i++) { JSONObject item=model.items.optJSONObject(i); if(item==null)continue;
            String text=(item.optString("name")+" "+item.optString("host")+" "+item.optString("post")).toLowerCase(Locale.ROOT);
            if((model.kind.equals("Todos")||model.kind.equals(item.optString("kind"))) && text.contains(query)) result.add(i);
        } return result;
    }
    private void updateSelection() {
        galleryCount.setText(model.selected.size()+" selecionados • "+filtered().size()+" resultados");
        selectionButton.setText("Baixar selecionados ("+model.selected.size()+")");
        selectionButton.setEnabled(!model.selected.isEmpty()&&!model.snapshot.optBoolean("busy")&&!model.pending);
    }
    private void renderGallery() {
        if(galleryList==null || tab!=1)return;
        galleryGeneration++; int generation=galleryGeneration; galleryList.removeAllViews();
        List<Integer> filtered=filtered(); int pages=Math.max(1,(filtered.size()+PAGE_SIZE-1)/PAGE_SIZE); model.page=Math.min(model.page,pages-1);
        LinearLayout navigation=row();
        Button previous=button("←",false,() -> { model.page--; renderGallery(); }); previous.setEnabled(model.page>0);
        Button next=button("→",false,() -> { model.page++; renderGallery(); }); next.setEnabled(model.page<pages-1);
        previous.setContentDescription("Página anterior da galeria");next.setContentDescription("Próxima página da galeria");
        TextView page=text((model.page+1)+" / "+pages,14,MUTED);page.setGravity(Gravity.CENTER);page.setContentDescription("Página "+(model.page+1)+" de "+pages);
        navigation.addView(previous,weighted()); navigation.addView(page,weighted()); navigation.addView(next,weighted()); galleryList.addView(navigation);
        LinearLayout pair=null;
        boolean grid=wide && getResources().getConfiguration().screenWidthDp>=800;
        for(int slot=model.page*PAGE_SIZE;slot<Math.min(filtered.size(),(model.page+1)*PAGE_SIZE);slot++) {
            int index=filtered.get(slot); JSONObject item=model.items.optJSONObject(index); LinearLayout card=card();
            CheckBox select=checkbox(item.optString("name"),model.selected.contains(index)); Ui.key(select,"selecionar_"+index);
            select.setOnCheckedChangeListener((b,checked) -> { if(checked)model.selected.add(index); else model.selected.remove(index); updateSelection(); }); card.addView(select);
            card.addView(text(item.optString("kind")+" • "+item.optString("post")+" • "+item.optString("host"),11,MUTED));
            ImageView preview=new ImageView(this); preview.setScaleType(ImageView.ScaleType.FIT_CENTER); preview.setBackground(background(BG)); preview.setImageResource(R.drawable.ic_buidl);
            preview.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);card.addView(preview,new LinearLayout.LayoutParams(-1,dp(190)));
            loadThumbnail(index,preview,generation);
            if(item.optString("kind").equals("Vídeos")) {Button video=button("Prévia do vídeo",false,() -> previewVideo(index));video.setCompoundDrawablesWithIntrinsicBounds(ui.icon("play",TEXT),null,null,null);video.setContentDescription("Ver prévia de "+item.optString("name"));card.addView(video);}
            Button origin=button("Abrir origem",false,() -> openUri(item.optString("origin")));origin.setContentDescription("Abrir origem de "+item.optString("name"));card.addView(origin);
            if(grid){if((slot-model.page*PAGE_SIZE)%2==0){pair=row();pair.setGravity(Gravity.TOP);galleryList.addView(pair);}LinearLayout.LayoutParams tile=weighted();tile.setMargins(dp(4),dp(8),dp(4),dp(8));pair.addView(card,tile);}else galleryList.addView(card);
        }
        if(filtered.isEmpty()) galleryList.addView(text("Nenhum arquivo neste filtro.",14,MUTED));
        updateSelection();
    }
    private void loadThumbnail(int index,ImageView view,int generation) {
        int queue=model.snapshot.optInt("queue_id"); String key=queue+":"+index;
        Bitmap cached=model.thumbnails.get(key); if(cached!=null) { view.setImageBitmap(cached); return; }
        model.images.execute(() -> {
            if(destroyed || generation!=galleryGeneration || model.engine==null)return;
            try {
                PyObject result=model.engine.callAttr("thumbnail",queue,index); if(result==null)return;
                byte[] data=result.toJava(byte[].class); if(data==null)return;
                BitmapFactory.Options options=new BitmapFactory.Options(); options.inJustDecodeBounds=true; BitmapFactory.decodeByteArray(data,0,data.length,options);
                if(options.outWidth<=0 || options.outHeight<=0 || (long)options.outWidth*options.outHeight>40_000_000)return;
                options.inSampleSize=1; while(options.outWidth/options.inSampleSize>480 || options.outHeight/options.inSampleSize>360)options.inSampleSize*=2;
                options.inJustDecodeBounds=false; Bitmap bitmap=BitmapFactory.decodeByteArray(data,0,data.length,options);
                if(bitmap==null)return; model.thumbnails.put(key,bitmap);
                handler.post(() -> { if(!destroyed && generation==galleryGeneration)view.setImageBitmap(bitmap); });
            } catch(Exception ignored) { }
        });
    }

    private void previewVideo(int index) {
        int queue=model.snapshot.optInt("queue_id"); LinearLayout panel=card();
        ImageView cover=new ImageView(this); cover.setScaleType(ImageView.ScaleType.FIT_CENTER); Bitmap bitmap=model.thumbnails.get(queue+":"+index);
        cover.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        if(bitmap!=null)cover.setImageBitmap(bitmap); else cover.setImageResource(R.drawable.ic_buidl);
        panel.addView(cover,new LinearLayout.LayoutParams(-1,dp(180)));
        TextView info=text("Carregando prévia sem áudio…",12,MUTED); panel.addView(info);
        VideoView video=new VideoView(this); video.setVisibility(View.GONE); panel.addView(video,new LinearLayout.LayoutParams(-1,dp(210)));
        Button play=button("Pausar / reproduzir",false,() -> { if(video.isPlaying())video.pause(); else video.start(); }); play.setEnabled(false); panel.addView(play);
        ScrollView previewScroll=new ScrollView(this);previewScroll.addView(panel);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Prévia do vídeo").setView(previewScroll).setNegativeButton("Voltar",null).create();
        activeVideoDialog=dialog;
        final boolean[] closed={false}, failed={false}; final Runnable[] timeout={null};
        Runnable fallback=() -> { failed[0]=true; if(timeout[0]!=null)handler.removeCallbacks(timeout[0]); video.stopPlayback(); video.setVisibility(View.GONE); cover.setVisibility(View.VISIBLE); play.setEnabled(false); info.setText("Prévia indisponível neste host. Mantivemos a capa; o arquivo ainda pode ser baixado."); };
        dialog.setOnDismissListener(d -> { closed[0]=true; video.stopPlayback(); if(timeout[0]!=null)handler.removeCallbacks(timeout[0]); }); dialog.show();
        video.setOnErrorListener((mp,what,extra) -> { fallback.run(); return true; });
        video.setOnPreparedListener(mp -> { if(closed[0]||failed[0])return; handler.removeCallbacks(timeout[0]); mp.setVolume(0,0); cover.setVisibility(View.GONE); video.setVisibility(View.VISIBLE); play.setEnabled(true); info.setText("Prévia sem áudio • usa dados da conexão"); video.start(); });
        timeout[0]=() -> { if(!closed[0])fallback.run(); }; handler.postDelayed(timeout[0],20000);
        model.images.execute(() -> {
            try {
                JSONObject result=new JSONObject(model.engine.callAttr("video_source",queue,index).toString());
                HashMap<String,String> headers=new HashMap<>(); JSONObject h=result.getJSONObject("headers"); java.util.Iterator<String> keys=h.keys(); while(keys.hasNext()){String k=keys.next();headers.put(k,h.getString(k));}
                handler.post(() -> { if(!closed[0]&&!failed[0]) { video.setVisibility(View.VISIBLE); video.setVideoURI(Uri.parse(result.optString("url")),headers); } });
            } catch(Exception e) { handler.post(() -> { if(!closed[0])fallback.run(); }); }
        });
    }

    private void showFiles() {
        content.addView(ui.heading("Seus arquivos",26));
        boolean externalDestination=!model.snapshot.optString("destination").isEmpty();
        content.addView(text(externalDestination ? "Arquivos salvos automaticamente na pasta escolhida. Para ver downloads anteriores, selecione a pasta usada em Baixar."
                : "Na pasta do aplicativo. Exportar cria uma cópia fora do BUIDL.",12,MUTED));
        if(externalDestination)content.addView(button("Abrir pasta escolhida",true,() -> {
            try { Uri tree=Uri.parse(model.snapshot.optString("destination"));
                Uri folder=DocumentsContract.buildDocumentUriUsingTree(tree,DocumentsContract.getTreeDocumentId(tree));
                startActivity(new Intent(Intent.ACTION_VIEW).setDataAndType(folder,DocumentsContract.Document.MIME_TYPE_DIR).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION));
            }catch(Exception e){message("Abra a pasta escolhida pelo gerenciador de arquivos do Android.");}
        }));
        else content.addView(button("Exportar arquivos para uma pasta",true,() -> {
            if(model.snapshot.optBoolean("busy")) { message("Aguarde o download terminar para exportar."); return; }
            startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION),PICK_EXPORT);
        }));
        content.addView(button("Atualizar lista",false,() -> showTab(2)));
        final LinearLayout listing=column(); content.addView(listing); listing.addView(text("Lendo arquivos…",12,MUTED));
        model.call("files",result -> {
            if(destroyed||tab!=2)return; listing.removeAllViews();
            try { JSONArray files=new JSONArray(result.toString());
                if(files.length()==0){LinearLayout empty=card();section(empty,"Tudo o que você guardar, aqui","folder");empty.addView(text("Ainda não há downloads nesta pasta. Escolha uma thread para começar.",15,MUTED));empty.addView(button("Escolher uma thread",true,() -> showTab(0)));listing.addView(empty);return;}
                listing.addView(text(files.length()+" arquivos • "+(externalDestination ? model.snapshot.optString("destination_label") : model.downloads),11,MUTED));
                int limit=Math.min(files.length(),150);
                for(int i=0;i<limit;i++){ JSONObject f=files.getJSONObject(i); LinearLayout c=card(); c.addView(text(f.getString("name"),14,TEXT));
                    c.addView(text(f.optString("relative")+"\n"+android.text.format.Formatter.formatFileSize(this,f.optLong("size")),10,MUTED));
                    Button open=button("Abrir / visualizar",false,() -> openFile(f));open.setContentDescription("Abrir arquivo "+f.optString("name"));c.addView(open);listing.addView(c); }
                if(files.length()>limit)listing.addView(text("Mostrando os primeiros 150. Os demais continuam na pasta de destino.",12,MUTED));
            }catch(Exception e){message(e.getMessage());}
        });
    }
    private void openFile(JSONObject file) {
        try { Uri uri=file.has("uri") ? Uri.parse(file.getString("uri")) : FileProvider.getUriForFile(this,getPackageName()+".files",new File(file.getString("path")));
            if(!"content".equals(uri.getScheme()))throw new IllegalArgumentException("URI inválida");
            startActivity(new Intent(Intent.ACTION_VIEW).setDataAndType(uri,file.getString("mime")).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION));
        }catch(Exception e){message("Não há um aplicativo compatível para abrir este arquivo. Você pode exportá-lo.");}
    }
    private void openUri(String url) { Uri uri=Uri.parse(url); if(!"https".equals(uri.getScheme())&&!"http".equals(uri.getScheme()))return;
        try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(Exception e){message("Não há navegador disponível.");} }
    private void showLogs() {
        JSONObject s=model.snapshot; StringBuilder details=new StringBuilder(); JSONArray errors=s.optJSONArray("errors"), logs=s.optJSONArray("logs");
        if(errors!=null && errors.length()>0){details.append("FALHAS / AVISOS\n\n");for(int i=0;i<errors.length();i++)details.append(errors.optString(i)).append("\n\n");}
        details.append("ATIVIDADE\n\n"); if(logs!=null)for(int i=0;i<logs.length();i++)details.append(logs.optString(i)).append("\n\n");
        TextView text=text(details.toString(),12,TEXT); text.setTextIsSelectable(true); ScrollView scroll=new ScrollView(this); scroll.setPadding(dp(16),0,dp(16),0);scroll.addView(text);
        new AlertDialog.Builder(this).setTitle("Atividade do BUIDL").setView(scroll).setPositiveButton("Fechar",null).show();
    }
    private void message(String text) { if(!destroyed) new AlertDialog.Builder(this).setMessage(text).setPositiveButton("OK",null).show(); }

    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if(request==CAPTURE_COOKIES) {
            if(result==RESULT_OK) message("Cookies salvos e prontos para uso. Se o site pedir login novamente, repita a captura.");
            return;
        }
        if(result!=RESULT_OK||data==null||data.getData()==null)return;
        Uri uri=data.getData();
        if(request==PICK_DESTINATION) {
            if(model.pending || model.snapshot.optBoolean("busy")) { message("Aguarde a operação terminar e escolha a pasta novamente."); return; }
            try {
                int grants=data.getFlags()&(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                if(grants!=(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION))throw new SecurityException();
                getContentResolver().takePersistableUriPermission(uri,grants);
                model.call("set_destination",unused -> {updateStatus();message("Pasta escolhida. Os próximos downloads serão salvos nela automaticamente.");},uri.toString());
            }catch(Exception e){message("Não foi possível obter permissão de escrita. Escolha outra pasta ou crie uma subpasta em Documentos/Downloads.");}
        } else if(request==PICK_COOKIES) {
            model.io.execute(() -> { File pending=new File(getFilesDir(),"cookies.pending");
                try(InputStream input=getContentResolver().openInputStream(uri); FileOutputStream output=new FileOutputStream(pending)) {
                    if(input==null)throw new IllegalArgumentException("Arquivo indisponível");
                    byte[] buffer=new byte[8192]; int size,total=0;
                    while((size=input.read(buffer))!=-1) { total+=size; if(total>2*1024*1024)throw new IllegalArgumentException("Cookies maiores que 2 MiB."); output.write(buffer,0,size); }
                    output.flush(); model.call("import_cookies",unused -> message("Cookies importados."),pending.getAbsolutePath());
                }catch(Exception e){model.error(e);pending.delete();}
            });
        } else if(request==PICK_EXPORT) {
            getContentResolver().takePersistableUriPermission(uri,data.getFlags()&(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION));
            TextView progress=text("Preparando exportação…",14,TEXT); progress.setPadding(dp(20),dp(20),dp(20),dp(20));
            AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Exportar arquivos").setView(progress).setCancelable(false).create();dialog.show();
            model.io.execute(() -> { String outcome;
                try { JSONArray files=new JSONArray(model.engine.callAttr("files").toString());
                    int copied=ExportFiles.copy(this,model.downloads,uri,files,(done,total) -> handler.post(() -> progress.setText(done+" / "+total+" arquivos exportados")));
                    outcome=copied+" arquivos exportados. Os originais foram mantidos no BUIDL.";
                }catch(Exception e){outcome="Não foi possível concluir a exportação: "+e.getMessage();}
                final String message=outcome;handler.post(() -> { if(!destroyed){dialog.dismiss();message(message);} });
            });
        }
    }
}
