# __init__.py
"""
Enhanced LM Studio Anki Integration
Features: Multi-field sources, processing metrics, error handling, retry logic
"""

import json
import urllib.request
import urllib.error
import time
import re
import logging
from datetime import datetime
from threading import Thread
from typing import Optional, List, Dict, Tuple
from aqt import mw, gui_hooks
from aqt.utils import showInfo, showWarning
from aqt.qt import *
from aqt.browser import Browser

# Configuration
LM_STUDIO_URL = "http://localhost:1234/v1"
API_KEY = "lm-studio"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProcessingMetrics:
    """Track processing statistics and metrics"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.start_time = time.time()
        self.total_cards = 0
        self.processed = 0
        self.successful = 0
        self.skipped = 0
        self.errors = 0
        self.retries = 0
        self.error_details = []
        self.processing_times = []
    
    def add_success(self, processing_time: float):
        self.successful += 1
        self.processed += 1
        self.processing_times.append(processing_time)
    
    def add_skip(self, reason: str):
        self.skipped += 1
        self.processed += 1
    
    def add_error(self, error_type: str, message: str, card_info: str = ""):
        self.errors += 1
        self.processed += 1
        self.error_details.append({
            'type': error_type,
            'message': message,
            'card': card_info,
            'time': datetime.now().strftime('%H:%M:%S')
        })
    
    def add_retry(self):
        self.retries += 1
    
    def get_elapsed_time(self) -> float:
        return time.time() - self.start_time
    
    def get_avg_processing_time(self) -> float:
        return sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0
    
    def get_cards_per_minute(self) -> float:
        elapsed = self.get_elapsed_time()
        return (self.processed / elapsed) * 60 if elapsed > 0 else 0
    
    def get_success_rate(self) -> float:
        return (self.successful / self.processed) * 100 if self.processed > 0 else 0

class LMStudioClient:
    """Enhanced LM Studio API client with retry logic"""
    
    def __init__(self):
        self.base_url = LM_STUDIO_URL
        self.api_key = API_KEY
        self.max_retries = 3
        self.retry_delay = 1.0
    
    def test_connection(self) -> bool:
        """Test if LM Studio is accessible"""
        try:
            response = self._request("/models", method="GET", timeout=10)
            return response is not None
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def get_models(self) -> List[str]:
        """Get available model IDs"""
        try:
            response = self._request("/models", method="GET", timeout=10)
            if response and "data" in response:
                return [model["id"] for model in response["data"]]
            return []
        except Exception as e:
            logger.error(f"Failed to get models: {e}")
            return []
    
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 200, 
                temperature: float = 0.3, selected_model: str = None) -> Tuple[Optional[str], str, int]:
        """
        Generate text with retry logic
        Returns: (result, error_message, retry_count)
        """
        models = self.get_models()
        if not models:
            return None, "No models available", 0
        
        model_to_use = selected_model if selected_model in models else models[0]
        
        payload = {
            "model": model_to_use,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        retry_count = 0
        last_error = ""
        
        for attempt in range(self.max_retries):
            try:
                response = self._request("/chat/completions", payload, timeout=60)
                if response and "choices" in response and response["choices"]:
                    content = response["choices"][0]["message"]["content"].strip()
                    return content, "", retry_count
                else:
                    last_error = "Empty response from API"
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
                if e.code == 429:  # Rate limit
                    time.sleep(self.retry_delay * (attempt + 1))
                elif e.code >= 500:  # Server error
                    time.sleep(self.retry_delay)
                else:
                    break  # Don't retry client errors
            except urllib.error.URLError as e:
                last_error = f"Connection error: {e.reason}"
                time.sleep(self.retry_delay)
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                time.sleep(self.retry_delay)
            
            retry_count += 1
            logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
        
        return None, last_error, retry_count
    
    def _request(self, endpoint: str, payload=None, method: str = "POST", timeout: int = 30):
        """Make HTTP request with timeout"""
        url = f"{self.base_url.rstrip('/')}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        if method == "GET":
            req = urllib.request.Request(url, headers=headers)
        else:
            data = json.dumps(payload).encode('utf-8') if payload else None
            req = urllib.request.Request(url, data=data, headers=headers)
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))

class ConnectionDialog(QDialog):
    """Enhanced connection test dialog"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.client = LMStudioClient()
        self.setup_ui()
        self.load_window_geometry()
        self.test_connection()
    
    def setup_ui(self):
        self.setWindowTitle("LM Studio Connection")
        self.setMinimumSize(400, 300)
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("LM Studio Connection Test")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Status
        self.status_label = QLabel("Testing connection...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Connection details
        self.details_label = QLabel("")
        self.details_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)
        
        # Models list
        models_label = QLabel("Available Models:")
        layout.addWidget(models_label)
        
        self.models_list = QListWidget()
        layout.addWidget(self.models_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.test_connection)
        button_layout.addWidget(refresh_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def test_connection(self):
        self.status_label.setText("Testing connection...")
        self.details_label.setText(f"Connecting to: {LM_STUDIO_URL}")
        self.models_list.clear()
        
        try:
            start_time = time.time()
            if self.client.test_connection():
                connection_time = time.time() - start_time
                models = self.client.get_models()
                
                if models:
                    self.status_label.setText("Connection successful!")
                    self.details_label.setText(f"Response time: {connection_time:.2f}s | Models found: {len(models)}")
                    
                    for model in models:
                        self.models_list.addItem(model)
                else:
                    self.status_label.setText("Connected but no models loaded")
                    self.details_label.setText("Please load a model in LM Studio")
            else:
                self.status_label.setText("Connection failed")
                self.details_label.setText("Make sure LM Studio is running and accessible")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
    
    def load_window_geometry(self):
        """Load saved window size and position"""
        config = mw.addonManager.getConfig(__name__) or {}
        geometry = config.get("connection_dialog_geometry")
        if geometry:
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
    
    def closeEvent(self, event):
        """Save window geometry on close"""
        config = mw.addonManager.getConfig(__name__) or {}
        config["connection_dialog_geometry"] = self.saveGeometry().toBase64().data().decode()
        mw.addonManager.writeConfig(__name__, config)
        event.accept()

class FieldConfigDialog(QDialog):
    """Enhanced field configuration dialog - now just target field"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_config()
        self.load_window_geometry()
    
    def setup_ui(self):
        self.setWindowTitle("Field Configuration")
        self.setMinimumSize(500, 400)
        self.resize(600, 500)
        
        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Content widget
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel("Field Configuration")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Information box about multi-field system
        info_text = """Multi-Field System

Use any field as a source in your prompts with placeholders like:
• {{Question}} - for Question field content
• {{Text}} - for Text field content
• {{Word}} - for Word field content

Example prompt: "Explain this concept: {{Question}} with context: {{Context}}"
        """
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Target field only now
        layout.addWidget(QLabel("Target Field (where to put generated content):"))
        self.target_field = QLineEdit()
        self.target_field.setPlaceholderText("e.g., Answer, Explanation, Notes, Definition")
        layout.addWidget(self.target_field)
        
        # Model selection
        layout.addWidget(QLabel("Preferred Model (optional):"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setPlaceholderText("Leave empty to use first available model")
        layout.addWidget(self.model_combo)
        
        # Load models button
        load_models_btn = QPushButton("Load Available Models")
        load_models_btn.clicked.connect(self.load_models)
        layout.addWidget(load_models_btn)
        
        # Processing options
        options_label = QLabel("Processing Options:")
        layout.addWidget(options_label)
        
        self.skip_existing = QCheckBox("Skip cards that already have content in target field")
        self.skip_existing.setChecked(True)
        layout.addWidget(self.skip_existing)
        
        self.backup_before = QCheckBox("Create backup before processing")
        self.backup_before.setChecked(True)
        layout.addWidget(self.backup_before)
        
        # Add stretch to push content to top
        layout.addStretch()
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # Fixed buttons at bottom
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(30, 15, 30, 15)
        button_layout.setSpacing(15)
        
        button_layout.addStretch()
        
        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        button_layout.addWidget(cancel_btn)
        
        main_layout.addWidget(button_widget)
    
    def load_models(self):
        """Load available models from LM Studio"""
        client = LMStudioClient()
        models = client.get_models()
        
        self.model_combo.clear()
        if models:
            self.model_combo.addItems(models)
            showInfo(f"Loaded {len(models)} models")
        else:
            showWarning("No models found. Make sure LM Studio is running with a model loaded.")
    
    def load_config(self):
        """Load field configuration"""
        config = mw.addonManager.getConfig(__name__) or {}
        self.target_field.setText(config.get("target_field", "Answer"))
        self.model_combo.setCurrentText(config.get("preferred_model", ""))
        self.skip_existing.setChecked(config.get("skip_existing", True))
        self.backup_before.setChecked(config.get("backup_before", True))
    
    def save_config(self):
        """Save field configuration"""
        if not self.target_field.text().strip():
            showWarning("Please specify the target field name.")
            return
        
        # Get existing config and update only fields
        config = mw.addonManager.getConfig(__name__) or {}
        config["target_field"] = self.target_field.text().strip()
        config["preferred_model"] = self.model_combo.currentText().strip()
        config["skip_existing"] = self.skip_existing.isChecked()
        config["backup_before"] = self.backup_before.isChecked()
        
        mw.addonManager.writeConfig(__name__, config)
        showInfo("Field configuration saved!")
        self.close()
    
    def load_window_geometry(self):
        """Load saved window size and position"""
        config = mw.addonManager.getConfig(__name__) or {}
        geometry = config.get("field_dialog_geometry")
        if geometry:
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
    
    def closeEvent(self, event):
        """Save window geometry on close"""
        config = mw.addonManager.getConfig(__name__) or {}
        config["field_dialog_geometry"] = self.saveGeometry().toBase64().data().decode()
        mw.addonManager.writeConfig(__name__, config)
        event.accept()

class PromptConfigDialog(QDialog):
    """Enhanced prompt configuration dialog with field placeholder system"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_config()
        self.load_window_geometry()
    
    def setup_ui(self):
        self.setWindowTitle("Prompt Configuration")
        self.setMinimumSize(700, 600)
        self.resize(850, 1000)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Content widget
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel("Prompt Configuration")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Field placeholder explanation
        placeholder_info = QLabel("""Field Placeholders

Use {{fieldname}} to insert content from any field. Examples:
• {{Question}} - inserts content from "Question" field
• {{Text}} - inserts content from "Text" field
• {{Context}} - inserts content from "Context" field
        """)
        placeholder_info.setWordWrap(True)
        layout.addWidget(placeholder_info)
        
        # System Prompt section
        system_group = QGroupBox("System Prompt")
        system_layout = QVBoxLayout(system_group)
        system_layout.setSpacing(15)
        
        system_layout.addWidget(QLabel("Define the AI's role and behavior:"))
        self.system_prompt = QTextEdit()
        self.system_prompt.setPlaceholderText("You are a helpful tutor. Provide clear, concise explanations for students...")
        system_layout.addWidget(self.system_prompt)
        
        # Temperature control
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Temperature:"))
        
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 200)
        self.temp_slider.setValue(0)
        self.temp_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.temp_slider.setTickInterval(50)
        self.temp_slider.valueChanged.connect(self.on_slider_changed)
        temp_layout.addWidget(self.temp_slider)
        
        self.temp_input = QLineEdit()
        self.temp_input.setFixedWidth(80)
        self.temp_input.setText("0.30")
        self.temp_input.textChanged.connect(self.on_input_changed)
        temp_layout.addWidget(self.temp_input)
        
        temp_info = QLabel("(0.0 = focused, 2.0 = creative)")
        temp_layout.addWidget(temp_info)
        
        system_layout.addLayout(temp_layout)
        layout.addWidget(system_group)
        
        # User Prompt section
        user_group = QGroupBox("User Prompt")
        user_layout = QVBoxLayout(user_group)
        user_layout.setSpacing(15)
        
        user_layout.addWidget(QLabel("Specific task instruction with field placeholders:"))
        self.user_prompt = QTextEdit()
        self.user_prompt.setPlaceholderText("Explain this concept: {{Question}}\n\nWith context: {{Context}}\n\nInclude:\n- Clear explanation\n- Key points\n- Examples")
        user_layout.addWidget(self.user_prompt)
        
        # Examples box
        example_text = """Example prompts:
• "Explain this concept: {{Question}} with context: {{Context}}"
• "Define {{Term}} and provide examples from {{Examples}}"
• "Analyze {{Text}} and summarize the main points"
        """
        example_label = QLabel(example_text)
        example_label.setWordWrap(True)
        user_layout.addWidget(example_label)
        
        layout.addWidget(user_group)
        
        # Generation Settings
        settings_group = QGroupBox("Generation Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        settings_layout.addWidget(QLabel("Maximum response length (tokens): -NOT WOKING YET LEAVE AT 200000"))
        self.max_tokens = QLineEdit()
        self.max_tokens.setPlaceholderText("200000")
        settings_layout.addWidget(self.max_tokens)
        
        settings_layout.addWidget(QLabel("Request timeout (seconds):"))
        self.timeout = QLineEdit()
        self.timeout.setPlaceholderText("60")
        settings_layout.addWidget(self.timeout)
        
        settings_layout.addWidget(QLabel("Max retries per card:"))
        self.max_retries = QLineEdit()
        self.max_retries.setPlaceholderText("3")
        settings_layout.addWidget(self.max_retries)
        
        layout.addWidget(settings_group)
        
        # Add stretch to push content to top
        layout.addStretch()
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # Fixed buttons at bottom
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(30, 15, 30, 15)
        button_layout.setSpacing(15)
        
        button_layout.addStretch()
        
        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        button_layout.addWidget(cancel_btn)
        
        main_layout.addWidget(button_widget)
    
    def on_slider_changed(self, value):
        """Update input box when slider changes"""
        temperature = value / 100.0
        self.temp_input.setText(f"{temperature:.2f}")
    
    def on_input_changed(self, text):
        """Update slider when input box changes"""
        try:
            temperature = float(text)
            if 0.0 <= temperature <= 2.0:
                self.temp_slider.setValue(int(temperature * 100))
        except ValueError:
            pass
    
    def load_config(self):
        """Load prompt configuration"""
        config = mw.addonManager.getConfig(__name__) or {}
        
        # Load system prompt and temperature
        self.system_prompt.setPlainText(config.get("system_prompt", 
            "You are a helpful tutor. Provide clear, concise explanations for students."))
        
        temperature = config.get("temperature", 0.3)
        self.temp_slider.setValue(int(temperature * 100))
        self.temp_input.setText(f"{temperature:.2f}")
        
        # Load user prompt
        self.user_prompt.setPlainText(config.get("user_prompt", 
            "Explain this concept: {{Question}}\n\nInclude:\n- Clear explanation\n- Key points\n- Examples"))
        
        # Load settings
        self.max_tokens.setText(str(config.get("max_tokens", 200)))
        self.timeout.setText(str(config.get("timeout", 60)))
        self.max_retries.setText(str(config.get("max_retries", 3)))
    
    def save_config(self):
        """Save prompt configuration"""
        try:
            temperature = float(self.temp_input.text())
            if not (0.0 <= temperature <= 2.0):
                showWarning("Temperature must be between 0.0 and 2.0")
                return
        except ValueError:
            showWarning("Please enter a valid temperature value")
            return
        
        if not self.system_prompt.toPlainText().strip():
            showWarning("Please enter a system prompt.")
            return
        
        if not self.user_prompt.toPlainText().strip():
            showWarning("Please enter a user prompt.")
            return
        
        # Check for field placeholders
        user_prompt_text = self.user_prompt.toPlainText()
        field_placeholders = re.findall(r'\{\{(\w+)\}\}', user_prompt_text)
        if not field_placeholders:
            if not self.confirm_no_placeholders():
                return
        
        try:
            max_tokens = int(self.max_tokens.text() or "200")
            timeout = int(self.timeout.text() or "60")
            max_retries = int(self.max_retries.text() or "3")
        except ValueError:
            showWarning("Please enter valid numbers for settings.")
            return
        
        # Get existing config and update prompts
        config = mw.addonManager.getConfig(__name__) or {}
        config["system_prompt"] = self.system_prompt.toPlainText().strip()
        config["user_prompt"] = user_prompt_text.strip()
        config["temperature"] = temperature
        config["max_tokens"] = max_tokens
        config["timeout"] = timeout
        config["max_retries"] = max_retries
        
        mw.addonManager.writeConfig(__name__, config)
        showInfo("Prompt configuration saved successfully!")
        self.close()
    
    def confirm_no_placeholders(self):
        """Confirm if user wants to save prompt without field placeholders"""
        reply = QMessageBox.question(
            self, 
            "No Field Placeholders", 
            "Your prompt doesn't contain any {{fieldname}} placeholders.\n\n"
            "This means the same prompt will be used for all cards.\n"
            "Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes
    
    def load_window_geometry(self):
        """Load saved window size and position"""
        config = mw.addonManager.getConfig(__name__) or {}
        geometry = config.get("prompt_dialog_geometry")
        if geometry:
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
    
    def closeEvent(self, event):
        """Save window geometry on close"""
        config = mw.addonManager.getConfig(__name__) or {}
        config["prompt_dialog_geometry"] = self.saveGeometry().toBase64().data().decode()
        mw.addonManager.writeConfig(__name__, config)
        event.accept()

class ProcessingDialog(QDialog):
    """Simple progress dialog with essential metrics only"""
    
    def __init__(self, total_cards, parent=None):
        super().__init__(parent)
        self.total_cards = total_cards
        self.metrics = ProcessingMetrics()
        self.metrics.total_cards = total_cards
        self.setup_ui()
        self.load_window_geometry()
    
    def setup_ui(self):
        self.setWindowTitle("Processing Cards")
        self.setFixedSize(450, 250)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title - no styling
        title = QLabel("Processing Cards")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Progress bar - no styling
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.total_cards)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Simple metrics layout
        metrics_widget = QWidget()
        metrics_layout = QGridLayout(metrics_widget)
        metrics_layout.setSpacing(10)
        
        # Row 1 - no styling
        self.generated_label = QLabel("Generated: 0")
        metrics_layout.addWidget(self.generated_label, 0, 0)
        
        self.errors_label = QLabel("Errors: 0")
        metrics_layout.addWidget(self.errors_label, 0, 1)
        
        # Row 2 - no styling
        self.elapsed_label = QLabel("Time: 0s")
        metrics_layout.addWidget(self.elapsed_label, 1, 0)
        
        self.remaining_label = QLabel("Remaining: --")
        metrics_layout.addWidget(self.remaining_label, 1, 1)
        
        layout.addWidget(metrics_widget)
        
        # Current card - no styling
        self.current_label = QLabel("Starting...")
        self.current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_label.setWordWrap(True)
        layout.addWidget(self.current_label)
        
        # Cancel button - no styling
        self.close_btn = QPushButton("Cancel")
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)
    
    def update_progress(self, processed, successful, current_text="", error_info=None):
        """Update progress (thread-safe)"""
        QTimer.singleShot(0, lambda: self._update_gui(processed, successful, current_text, error_info))
    
    def _update_gui(self, processed, successful, current_text, error_info):
        """Update GUI elements (main thread only)"""
        self.progress_bar.setValue(processed)
        
        # Update simple metrics
        self.generated_label.setText(f"Generated: {successful}")
        self.errors_label.setText(f"Errors: {self.metrics.errors}")
        
        # Update time
        elapsed = self.metrics.get_elapsed_time()
        self.elapsed_label.setText(f"Time: {elapsed:.0f}s")
        
        # Calculate remaining time
        if processed > 0:
            avg_time = elapsed / processed
            remaining_cards = self.total_cards - processed
            remaining_time = avg_time * remaining_cards
            self.remaining_label.setText(f"Remaining: {remaining_time:.0f}s")
        
        # Update current card
        if current_text:
            display_text = current_text[:50] + "..." if len(current_text) > 50 else current_text
            self.current_label.setText(f"Processing: {display_text}")
    
    def load_window_geometry(self):
        """Load saved window size and position"""
        config = mw.addonManager.getConfig(__name__) or {}
        geometry = config.get("processing_dialog_geometry")
        if geometry:
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
    
    def closeEvent(self, event):
        """Save window geometry on close"""
        config = mw.addonManager.getConfig(__name__) or {}
        config["processing_dialog_geometry"] = self.saveGeometry().toBase64().data().decode()
        mw.addonManager.writeConfig(__name__, config)
        event.accept()

class WorkerThread(QThread):
    """Enhanced background thread for processing cards with metrics"""
    
    progress_updated = pyqtSignal(int, int, str, object)  # processed, successful, current_text, error_info
    finished = pyqtSignal(object)  # metrics object
    
    def __init__(self, client, card_ids, config, metrics):
        super().__init__()
        self.client = client
        self.card_ids = card_ids
        self.config = config
        self.metrics = metrics
    
    def run(self):
        """Process cards in background thread with enhanced error handling"""
        for card_id in self.card_ids:
            try:
                self.process_single_card(card_id)
            except Exception as e:
                logger.error(f"Unexpected error processing card {card_id}: {e}")
                self.metrics.add_error("Unexpected", str(e), f"Card ID: {card_id}")
                self.progress_updated.emit(
                    self.metrics.processed, 
                    self.metrics.successful, 
                    "", 
                    self.metrics.error_details[-1] if self.metrics.error_details else None
                )
        
        self.finished.emit(self.metrics)
    
    def process_single_card(self, card_id):
        """Process a single card with detailed tracking"""
        start_time = time.time()
        
        card = mw.col.getCard(card_id)
        note = card.note()
        
        # Get field names and target field
        field_names = [field['name'] for field in note.model()['flds']]
        target_field = self.config["target_field"]
        
        if target_field not in field_names:
            self.metrics.add_error("Config", f"Target field '{target_field}' not found", f"Card ID: {card_id}")
            self.progress_updated.emit(
                self.metrics.processed, 
                self.metrics.successful, 
                "Field not found", 
                self.metrics.error_details[-1]
            )
            return
        
        target_index = field_names.index(target_field)
        
        # Skip if target already has content (if option is enabled)
        if self.config.get("skip_existing", True) and note.fields[target_index].strip():
            self.metrics.add_skip("Target field already has content")
            self.progress_updated.emit(self.metrics.processed, self.metrics.successful, "Skipping: has content", None)
            return
        
        # Process field placeholders in user prompt
        user_prompt = self.process_field_placeholders(note, field_names)
        if not user_prompt:
            self.metrics.add_skip("No valid field content found")
            self.progress_updated.emit(self.metrics.processed, self.metrics.successful, "Skipping: no content", None)
            return
        
        # Show current processing
        preview_text = self.get_preview_text(note, field_names)
        self.progress_updated.emit(self.metrics.processed, self.metrics.successful, preview_text, None)
        
        # Generate explanation with retry logic
        explanation, error_msg, retry_count = self.client.generate(
            self.config["system_prompt"],
            user_prompt,
            self.config.get("max_tokens", 200),
            self.config.get("temperature", 0.3),
            self.config.get("preferred_model")
        )
        
        self.metrics.retries += retry_count
        
        if explanation:
            note.fields[target_index] = explanation
            note.flush()
            processing_time = time.time() - start_time
            self.metrics.add_success(processing_time)
        else:
            self.metrics.add_error("Generation", error_msg, preview_text)
            self.progress_updated.emit(
                self.metrics.processed, 
                self.metrics.successful, 
                "", 
                self.metrics.error_details[-1]
            )
            return
        
        self.progress_updated.emit(self.metrics.processed, self.metrics.successful, "", None)
    
    def process_field_placeholders(self, note, field_names):
        """Process {{fieldname}} placeholders in user prompt"""
        user_prompt = self.config["user_prompt"]
        
        # Find all placeholders
        placeholders = re.findall(r'\{\{(\w+)\}\}', user_prompt)
        
        if not placeholders:
            # No placeholders, return prompt as-is
            return user_prompt
        
        # Check if all referenced fields exist and have content
        field_values = {}
        for placeholder in placeholders:
            if placeholder not in field_names:
                logger.warning(f"Field '{placeholder}' not found in note")
                return None
            
            field_index = field_names.index(placeholder)
            field_content = note.fields[field_index].strip()
            
            if not field_content:
                logger.info(f"Field '{placeholder}' is empty")
                return None
            
            field_values[placeholder] = field_content
        
        # Replace placeholders
        processed_prompt = user_prompt
        for placeholder, value in field_values.items():
            processed_prompt = processed_prompt.replace(f"{{{{{placeholder}}}}}", value)
        
        return processed_prompt
    
    def get_preview_text(self, note, field_names):
        """Get preview text for progress display"""
        # Try to get content from first non-empty field
        for field_name in field_names:
            field_index = field_names.index(field_name)
            content = note.fields[field_index].strip()
            if content:
                return content[:50]
        return "Card content"

class LMStudioAddon:
    """Enhanced main addon class"""
    
    def __init__(self):
        self.client = LMStudioClient()
        gui_hooks.browser_menus_did_init.append(self.setup_browser_menu)
    
    def setup_browser_menu(self, browser: Browser):
        """Add enhanced menu to browser"""
        menu = QMenu("LM Studio", browser.form.menubar)
        
        # Test connection
        test_action = QAction("Test Connection", browser)
        test_action.triggered.connect(self.show_connection_test)
        menu.addAction(test_action)
        
        menu.addSeparator()
        
        # Configuration
        fields_action = QAction("Configure Fields", browser)
        fields_action.triggered.connect(self.show_field_config)
        menu.addAction(fields_action)
        
        prompts_action = QAction("Configure Prompts", browser)
        prompts_action.triggered.connect(self.show_prompt_config)
        menu.addAction(prompts_action)
        
        menu.addSeparator()
        
        # Processing
        process_action = QAction("Process Selected Cards", browser)
        process_action.triggered.connect(lambda: self.process_cards(browser))
        menu.addAction(process_action)
        
        browser.form.menubar.addMenu(menu)
    
    def show_connection_test(self):
        """Show connection test dialog"""
        dialog = ConnectionDialog(mw)
        dialog.exec()
    
    def show_field_config(self):
        """Show field configuration dialog"""
        dialog = FieldConfigDialog(mw)
        dialog.exec()
    
    def show_prompt_config(self):
        """Show prompt configuration dialog"""
        dialog = PromptConfigDialog(mw)
        dialog.exec()
    
    def process_cards(self, browser: Browser):
        """Process selected cards with enhanced error handling and metrics"""
        card_ids = browser.selectedCards()
        if not card_ids:
            showWarning("Please select some cards first.")
            return
        
        # Validate configuration
        config = mw.addonManager.getConfig(__name__) or {}
        validation_error = self.validate_config(config)
        if validation_error:
            showWarning(validation_error)
            return
        
        # Test connection
        if not self.client.test_connection():
            showWarning("Cannot connect to LM Studio.\nPlease ensure it's running with a model loaded.")
            return
        
        # Create backup if requested
        if config.get("backup_before", True):
            try:
                # Create a checkpoint that can be undone
                mw.checkpoint("LM Studio Processing")
                logger.info("Checkpoint created successfully")
            except Exception as e:
                logger.error(f"Failed to create checkpoint: {e}")
                reply = QMessageBox.question(
                    mw,
                    "Backup Failed",
                    f"Failed to create checkpoint: {e}\n\nContinue processing anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return
        
        # Initialize metrics and show progress dialog
        current_metrics = ProcessingMetrics()
        current_metrics.total_cards = len(card_ids)
        
        self.progress_dialog = ProcessingDialog(len(card_ids), mw)
        self.progress_dialog.metrics = current_metrics
        self.progress_dialog.show()
        
        # Start background processing
        self.worker = WorkerThread(self.client, card_ids, config, current_metrics)
        self.worker.progress_updated.connect(self.progress_dialog.update_progress)
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.start()
    
    def validate_config(self, config):
        """Validate configuration before processing"""
        if not config.get("target_field"):
            return "Please configure the target field first.\nGo to: LM Studio → Configure Fields"
        
        if not config.get("system_prompt") or not config.get("user_prompt"):
            return "Please configure prompts first.\nGo to: LM Studio → Configure Prompts"
        
        # Check for field placeholders in user prompt
        user_prompt = config.get("user_prompt", "")
        placeholders = re.findall(r'\{\{(\w+)\}\}', user_prompt)
        
        if placeholders:
            logger.info(f"Found field placeholders: {placeholders}")
        else:
            logger.warning("No field placeholders found in user prompt")
        
        return None
    
    def on_processing_finished(self, metrics):
        """Handle processing completion with simple summary"""
        self.progress_dialog.close()
        
        # Refresh UI without schema change
        mw.requireReset()
        
        # Show simple results summary
        result_msg = f"Processing Complete!\n\n"
        result_msg += f"Total: {metrics.total_cards}\n"
        result_msg += f"Generated: {metrics.successful}\n"
        result_msg += f"Errors: {metrics.errors}\n"
        result_msg += f"Time: {metrics.get_elapsed_time():.1f}s"
        
        showInfo(result_msg)

# Initialize addon
def init_addon():
    global addon_instance
    addon_instance = LMStudioAddon()

gui_hooks.main_window_did_init.append(lambda: init_addon())
addon_instance = None