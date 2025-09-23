# interface.py
import pygame
import time
import json
import qrcode
import io
import socket
import os

from settings import (
    DEBUG, COCKTAILS_FILE, LOGO_FOLDER, ML_COEFFICIENT, 
    RETRACTION_TIME, PUMP_CONCURRENCY, INVERT_PUMP_PINS, 
    FULL_SCREEN, COCKTAIL_IMAGE_SCALE
)

# Configuration flags
ALLOW_FAVORITES = True  # Enable/disable favorite functionality
SHOW_RELOAD_COCKTAILS_BUTTON = True  # Show/hide reload cocktails button
RELOAD_COCKTAILS_TIMEOUT = None  # Auto-reload timeout (None = disabled)
CONFIG_FILE = "pump_config.json"  # Pump configuration file
from helpers import get_cocktail_image_path, get_valid_cocktails, wrap_text, favorite_cocktail, unfavorite_cocktail
from controller import make_drink

import logging
logger = logging.getLogger(__name__)

class CustomDropdown:
    """Custom dropdown implementation to replace pygame_widgets"""
    def __init__(self, x, y, width, height, options, current_value="", font_size=18):
        self.rect = pygame.Rect(x, y, width, height)
        self.options = options
        self.current_value = current_value
        self.font = pygame.font.SysFont(None, font_size)
        self.is_open = False
        self.selected_index = 0
        self.scroll_offset = 0
        self.max_visible_items = 5
        self.item_height = 30
        
        # Find current value index
        if current_value in options:
            self.selected_index = options.index(current_value)
    
    def handle_event(self, event):
        """Handle mouse events for the dropdown"""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.is_open = not self.is_open
                return True
            elif self.is_open:
                # Check if clicking on dropdown items
                dropdown_rect = pygame.Rect(
                    self.rect.x, 
                    self.rect.y + self.rect.height,
                    self.rect.width, 
                    min(len(self.options), self.max_visible_items) * self.item_height
                )
                if dropdown_rect.collidepoint(event.pos):
                    # Calculate which item was clicked
                    relative_y = event.pos[1] - dropdown_rect.y
                    item_index = relative_y // self.item_height + self.scroll_offset
                    if 0 <= item_index < len(self.options):
                        self.selected_index = item_index
                        self.current_value = self.options[item_index]
                        self.is_open = False
                        return True
                else:
                    self.is_open = False
        
        elif event.type == pygame.MOUSEWHEEL and self.is_open:
            # Handle scrolling in dropdown
            dropdown_rect = pygame.Rect(
                self.rect.x, 
                self.rect.y + self.rect.height,
                self.rect.width, 
                min(len(self.options), self.max_visible_items) * self.item_height
            )
            if dropdown_rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll_offset = max(0, min(
                    len(self.options) - self.max_visible_items,
                    self.scroll_offset - event.y
                ))
                return True
        
        return False
    
    def draw(self, surface):
        """Draw the dropdown"""
        # Draw main dropdown button
        pygame.draw.rect(surface, (240, 240, 240), self.rect)
        pygame.draw.rect(surface, (100, 100, 100), self.rect, 2)
        
        # Draw current selection text
        display_text = self.current_value if self.current_value else "Select..."
        if len(display_text) > 20:
            display_text = display_text[:17] + "..."
        text_surface = self.font.render(display_text, True, (0, 0, 0))
        text_rect = text_surface.get_rect(center=(self.rect.centerx, self.rect.centery))
        surface.blit(text_surface, text_rect)
        
        # Draw dropdown arrow
        arrow_points = [
            (self.rect.right - 20, self.rect.centery - 5),
            (self.rect.right - 10, self.rect.centery + 5),
            (self.rect.right - 30, self.rect.centery + 5)
        ]
        pygame.draw.polygon(surface, (0, 0, 0), arrow_points)
        
        # Draw dropdown list if open
        if self.is_open:
            visible_items = min(len(self.options), self.max_visible_items)
            dropdown_rect = pygame.Rect(
                self.rect.x, 
                self.rect.y + self.rect.height,
                self.rect.width, 
                visible_items * self.item_height
            )
            
            # Draw dropdown background
            pygame.draw.rect(surface, (255, 255, 255), dropdown_rect)
            pygame.draw.rect(surface, (100, 100, 100), dropdown_rect, 2)
            
            # Draw items
            for i in range(visible_items):
                item_index = i + self.scroll_offset
                if item_index >= len(self.options):
                    break
                    
                item_rect = pygame.Rect(
                    dropdown_rect.x,
                    dropdown_rect.y + i * self.item_height,
                    dropdown_rect.width,
                    self.item_height
                )
                
                # Highlight selected item
                if item_index == self.selected_index:
                    pygame.draw.rect(surface, (200, 220, 255), item_rect)
                
                # Highlight hovered item
                mouse_pos = pygame.mouse.get_pos()
                if item_rect.collidepoint(mouse_pos):
                    pygame.draw.rect(surface, (230, 240, 255), item_rect)
                
                # Draw item text
                item_text = self.options[item_index]
                if len(item_text) > 25:
                    item_text = item_text[:22] + "..."
                text_surface = self.font.render(item_text, True, (0, 0, 0))
                text_rect = text_surface.get_rect(center=item_rect.center)
                surface.blit(text_surface, text_rect)
                
                # Draw separator line
                if i < visible_items - 1:
                    pygame.draw.line(surface, (200, 200, 200), 
                                   (item_rect.left, item_rect.bottom), 
                                   (item_rect.right, item_rect.bottom))
            
            # Draw scrollbar if needed
            if len(self.options) > self.max_visible_items:
                scrollbar_rect = pygame.Rect(
                    dropdown_rect.right - 10,
                    dropdown_rect.y,
                    10,
                    dropdown_rect.height
                )
                pygame.draw.rect(surface, (200, 200, 200), scrollbar_rect)
                
                # Calculate scrollbar thumb
                thumb_height = max(20, dropdown_rect.height * self.max_visible_items // len(self.options))
                thumb_y = dropdown_rect.y + (dropdown_rect.height - thumb_height) * self.scroll_offset // (len(self.options) - self.max_visible_items)
                thumb_rect = pygame.Rect(scrollbar_rect.x, thumb_y, scrollbar_rect.width, thumb_height)
                pygame.draw.rect(surface, (100, 100, 100), thumb_rect)
    
    def get_selected(self):
        """Get the currently selected value"""
        return self.current_value

def get_local_ip():
    """Get the local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "localhost"

def create_qr_code_slide():
    """Create a QR code slide for the Streamlit app access"""
    # Get local IP and port
    local_ip = get_local_ip()
    streamlit_port = 8501
    url = f"http://{local_ip}:{streamlit_port}"
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    # Create QR code image
    qr_image = qr.make_image(fill_color="black", back_color="white")
    
    # Convert PIL image to pygame surface
    img_buffer = io.BytesIO()
    qr_image.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    # Load into pygame
    qr_surface = pygame.image.load(img_buffer)
    
    # Scale to fit screen (make it large enough to scan easily)
    qr_size = min(screen_width, screen_height) // 2
    qr_surface = pygame.transform.scale(qr_surface, (qr_size, qr_size))
    
    # Create a cocktail-like object for the QR code slide
    qr_cocktail = {
        'normal_name': 'Access App',
        'fun_name': 'Scan QR Code',
        'qr_surface': qr_surface,
        'url': url,
        'is_qr_slide': True
    }
    
    return qr_cocktail

def get_cocktails_with_qr():
    """Get valid cocktails and add QR code slide at the end"""
    cocktails = get_valid_cocktails()
    qr_cocktail = create_qr_code_slide()
    cocktails.append(qr_cocktail)
    return cocktails

def check_for_refresh_signal():
    """Check if there's a signal from the app to refresh cocktails"""
    try:
        if os.path.exists('interface_signal.json'):
            with open('interface_signal.json', 'r') as f:
                signal = json.load(f)
            
            # Check if it's a refresh signal
            if signal.get('action') == 'refresh_cocktails':
                # Remove the signal file after reading
                os.remove('interface_signal.json')
                logger.info("Received refresh signal from app")
                return True
    except Exception as e:
        logger.error(f"Error checking refresh signal: {e}")
    
    return False

pygame.init()
if FULL_SCREEN:
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
else:
    screen = pygame.display.set_mode((720, 720))
screen_size = screen.get_size()
screen_width, screen_height = screen_size
# Überschreibe COCKTAIL_IMAGE_SCALE für 20% kleinere Bilder
COCKTAIL_IMAGE_SCALE = 0.70
cocktail_image_offset = screen_width * (1.0 - COCKTAIL_IMAGE_SCALE) // 2
pygame.display.set_caption('Cocktail Swipe')

normal_text_size = 48
small_text_size = int(normal_text_size * 0.6)
text_position = (screen_width // 2, int(screen_height * 0.82))

def add_layer(*args, function=screen.blit, key=None):
    if key == None:
        key = len(layers)
    layers[str(key)] = {'function': function, 'args': args}

def remove_layer(key):
    try:
        del layers[key]
    except KeyError:
        pass
    
layers = {}
def draw_frame():
    for layer in layers.values():
        layer['function'](*layer['args'])
    pygame.display.flip()

def animate_logo_click(logo, rect, base_size, target_size, layer_key, duration=150):
    """Animate a logo click (pop effect): grow from base_size to target_size then shrink back."""
    clock = pygame.time.Clock()
    center = rect.center
    # Expand
    start_time = pygame.time.get_ticks()
    while True:
        elapsed = pygame.time.get_ticks() - start_time
        progress = min(elapsed / duration, 1.0)
        current_size = int(base_size + (target_size - base_size) * progress)
        scaled_img = pygame.transform.scale(logo, (current_size, current_size))
        new_rect = scaled_img.get_rect(center=center)
        add_layer(scaled_img, new_rect, key=layer_key)
        draw_frame()
        if progress >= 1.0:
            break
        clock.tick(60)
    # Shrink back
    start_time = pygame.time.get_ticks()
    while True:
        elapsed = pygame.time.get_ticks() - start_time
        progress = min(elapsed / duration, 1.0)
        current_size = int(target_size - (target_size - base_size) * progress)
        scaled_img = pygame.transform.scale(logo, (current_size, current_size))
        new_rect = scaled_img.get_rect(center=center)
        add_layer(scaled_img, new_rect, key=layer_key)
        draw_frame()
        if progress >= 1.0:
            break
        clock.tick(60)

def animate_logo_rotate(logo, rect, layer_key, rotation=180):
    """Animate a logo click (rotate effect): rotate the amount of rotation provided"""
    angle = 0
    while angle < rotation:
        angle = (angle + 5) % 360
        rotated_loading = pygame.transform.rotate(logo, angle * -1)
        rotated_rect = rotated_loading.get_rect(center=rect.center)
        # Draw loading image first (under)
        add_layer(rotated_loading, rotated_rect, key=layer_key)
        draw_frame()

def animate_both_logos_zoom(single_logo, double_logo, single_rect, double_rect, base_size, target_size, duration=300):
    """Animate both logos zooming in together and then shrinking back."""
    clock = pygame.time.Clock()
    center_single = single_rect.center
    center_double = double_rect.center
    # Expand
    start_time = pygame.time.get_ticks()
    while True:
        elapsed = pygame.time.get_ticks() - start_time
        progress = min(elapsed / duration, 1.0)
        current_size = int(base_size + (target_size - base_size) * progress)
        scaled_single = pygame.transform.scale(single_logo, (current_size, current_size))
        scaled_double = pygame.transform.scale(double_logo, (current_size, current_size))
        new_rect_single = scaled_single.get_rect(center=center_single)
        new_rect_double = scaled_double.get_rect(center=center_double)
        add_layer(scaled_single, new_rect_single, key='single_logo')
        add_layer(scaled_double, new_rect_double, key='double_logo')
        draw_frame()
        if progress >= 1.0:
            break
        clock.tick(60)
    # Contract
    start_time = pygame.time.get_ticks()
    while True:
        elapsed = pygame.time.get_ticks() - start_time
        progress = min(elapsed / duration, 1.0)
        current_size = int(target_size - (target_size - base_size) * progress)
        scaled_single = pygame.transform.scale(single_logo, (current_size, current_size))
        scaled_double = pygame.transform.scale(double_logo, (current_size, current_size))
        new_rect_single = scaled_single.get_rect(center=center_single)
        new_rect_double = scaled_double.get_rect(center=center_double)
        add_layer(scaled_single, new_rect_single, key='single_logo')
        add_layer(scaled_double, new_rect_double, key='double_logo')
        draw_frame()
        if progress >= 1.0:
            break
        clock.tick(60)

def show_pouring_and_loading(watcher):
    """Overlay pouring_img full screen and a spinning loading_img (720x720) drawn underneath."""
    try:
        pouring_img = pygame.image.load('pouring.png')
        pouring_img = pygame.transform.scale(pouring_img, screen_size)
    except Exception as e:
        logger.exception('Error loading pouring.png')
        pouring_img = None
    try:
        loading_img = pygame.image.load('loading.png')
        loading_img = pygame.transform.scale(loading_img, (70, 70))
    except Exception as e:
        logger.exception('Error loading loading.png')
        loading_img = None
    try:
        checkmark_img = pygame.image.load('checkmark.png')
        checkmark_img = pygame.transform.scale(checkmark_img, (30, 30))
    except Exception as e:
        logger.exception('Error loading loading.png')
        checkmark_img = None
        
    angle = 0

    # Add a background layer
    add_layer(*layers['background']['args'], function=layers['background']['function'], key='pouring_background')
    # Then draw pouring image on top
    if pouring_img:
        add_layer(pouring_img, (0, -150), key='pouring')

    pour_layers = []
    pouring_line = 0
    while not watcher.done():
        angle = (angle - 5) % 360
        if loading_img:
            rotated_loading = pygame.transform.rotate(loading_img, angle)
        
        for index, pour in enumerate(watcher.pours):
            layer_key = f'pour_{index}'
            logo_layer_key = f'{layer_key}_logo'
            
            x_position = screen_width // 3
            y_position = (text_position[1] + small_text_size * pouring_line) - 325

            if logo_layer_key not in pour_layers:
                font = pygame.font.SysFont(None, small_text_size)
                for layer_index, line in enumerate(wrap_text(str(pour), font, screen_width * 0.5)):
                    line_key = f'{layer_key}_{layer_index}'
                    text_surface = font.render(line, True, (255, 255, 255))
                    line_y_position = y_position + small_text_size * layer_index
                    if layer_index > 0:
                        line_y_position = line_y_position - 10 * layer_index
                    text_rect = text_surface.get_rect(topleft=(x_position, line_y_position))
                    pour_layers.append(line_key)
                    add_layer(text_surface, text_rect, key=line_key)
                    pouring_line += 1
                pour_layers.append(logo_layer_key)

            status_position = layers.get(logo_layer_key, {}).get('args', [None, None])[1]
            if status_position:
                status_position = status_position.center
            else:
                status_position = (x_position - small_text_size // 2, y_position - 7 + small_text_size // 2)

            if pour.running and loading_img:
                rect = rotated_loading.get_rect(center=status_position)
                add_layer(rotated_loading, rect, key=logo_layer_key)
            else:
                if checkmark_img:
                    rect = checkmark_img.get_rect(center=status_position)
                    add_layer(checkmark_img, rect, key=logo_layer_key)
                else:
                    remove_layer(logo_layer_key)
                    

        draw_frame()

    for layer in pour_layers:
        remove_layer(layer)

    remove_layer('pouring')
    remove_layer('pouring_background')
    draw_frame()
    pygame.event.clear()  # Drop all events that happened while pouring

def create_settings_tray():
    """Create the settings tray UI elements"""
    tray_height = int(screen_height * 0.4)  # 40% of screen height
    tray_rect = pygame.Rect(0, screen_height - tray_height, screen_width, tray_height)
    
    # Create a semi-transparent background
    overlay = pygame.Surface((screen_width, tray_height))
    overlay.set_alpha(200)
    overlay.fill((0, 0, 0))
    
    # Settings title
    title_font = pygame.font.SysFont(None, 48)
    title_text = title_font.render("Settings", True, (255, 255, 255))
    title_rect = title_text.get_rect(center=(screen_width // 2, screen_height - tray_height + 40))
    
    # Time per 50ml slider (easier to measure than 1ml)
    slider_width = int(screen_width * 0.6)
    slider_height = 20
    slider_x = (screen_width - slider_width) // 2
    slider_y = screen_height - tray_height + 100
    
    # Slider background
    slider_bg_rect = pygame.Rect(slider_x, slider_y, slider_width, slider_height)
    
    # Convert ML_COEFFICIENT (time per 1ml) to time per 50ml for display
    # ML_COEFFICIENT is seconds per 1ml, so time per 50ml = ML_COEFFICIENT * 50
    time_per_50ml = ML_COEFFICIENT * 50
    
    # Slider range: 5-50 seconds for 50ml (equivalent to 0.1-1.0 seconds per 1ml)
    min_val_50ml, max_val_50ml = 5.0, 50.0
    slider_handle_x = slider_x + (time_per_50ml - min_val_50ml) / (max_val_50ml - min_val_50ml) * slider_width
    slider_handle_rect = pygame.Rect(slider_handle_x - 10, slider_y - 5, 20, 30)
    
    # Slider label
    slider_font = pygame.font.SysFont(None, 32)
    slider_label = slider_font.render(f"Time per 50ml: {time_per_50ml:.1f}s", True, (255, 255, 255))
    slider_label_rect = slider_label.get_rect(center=(screen_width // 2, slider_y - 30))
    
    # Buttons
    button_width = 150
    button_height = 50
    button_spacing = 20
    
    # Prime pumps button
    prime_rect = pygame.Rect(screen_width // 2 - button_width - button_spacing // 2, 
                           screen_height - tray_height + 180, button_width, button_height)
    prime_font = pygame.font.SysFont(None, 28)
    prime_text = prime_font.render("Prime Pumps", True, (255, 255, 255))
    prime_text_rect = prime_text.get_rect(center=prime_rect.center)
    
    # Clean pumps button
    clean_rect = pygame.Rect(screen_width // 2 + button_spacing // 2, 
                           screen_height - tray_height + 180, button_width, button_height)
    clean_font = pygame.font.SysFont(None, 28)
    clean_text = clean_font.render("Clean Pumps", True, (255, 255, 255))
    clean_text_rect = clean_text.get_rect(center=clean_rect.center)
    
    # Reverse pump direction toggle switch
    switch_width = 60
    switch_height = 30
    switch_x = screen_width // 2 - switch_width // 2
    switch_y = screen_height - tray_height + 250
    
    switch_rect = pygame.Rect(switch_x, switch_y, switch_width, switch_height)
    
    # Switch label
    switch_font = pygame.font.SysFont(None, 24)
    switch_label = switch_font.render("Reverse Pump Direction", True, (255, 255, 255))
    switch_label_rect = switch_label.get_rect(center=(screen_width // 2, switch_y - 20))
    
    # Streamlit app access info
    import socket
    try:
        # Get local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "localhost"
    
    streamlit_port = 8501  # Default Streamlit port
    
    # Access info label
    access_font = pygame.font.SysFont(None, 20)
    access_label = access_font.render("Access your app at:", True, (200, 200, 200))
    access_label_rect = access_label.get_rect(center=(screen_width // 2, switch_y + 50))
    
    # IP and port info
    ip_font = pygame.font.SysFont(None, 24)
    ip_text = f"http://{local_ip}:{streamlit_port}"
    ip_label = ip_font.render(ip_text, True, (0, 255, 255))  # Cyan color for URL
    ip_label_rect = ip_label.get_rect(center=(screen_width // 2, switch_y + 75))
    
    return {
        'tray_rect': tray_rect,
        'overlay': overlay,
        'title_text': title_text,
        'title_rect': title_rect,
        'slider_bg_rect': slider_bg_rect,
        'slider_handle_rect': slider_handle_rect,
        'slider_label': slider_label,
        'slider_label_rect': slider_label_rect,
        'prime_rect': prime_rect,
        'prime_text': prime_text,
        'prime_text_rect': prime_text_rect,
        'clean_rect': clean_rect,
        'clean_text': clean_text,
        'clean_text_rect': clean_text_rect,
        'switch_rect': switch_rect,
        'switch_label': switch_label,
        'switch_label_rect': switch_label_rect,
        'access_label': access_label,
        'access_label_rect': access_label_rect,
        'ip_label': ip_label,
        'ip_label_rect': ip_label_rect,
        'slider_x': slider_x,
        'slider_width': slider_width,
        'min_val': min_val_50ml,
        'max_val': max_val_50ml
    }

def draw_settings_tray(settings_ui, is_visible):
    """Draw the settings tray if visible"""
    if not is_visible:
        return
    
    # Draw overlay
    add_layer(settings_ui['overlay'], settings_ui['tray_rect'], key='settings_overlay')
    
    # Draw title
    add_layer(settings_ui['title_text'], settings_ui['title_rect'], key='settings_title')
    
    # Create temporary surfaces for slider and buttons
    temp_surface = pygame.Surface(screen_size, pygame.SRCALPHA)
    
    # Draw slider background
    pygame.draw.rect(temp_surface, (100, 100, 100), settings_ui['slider_bg_rect'])
    
    # Draw slider handle
    pygame.draw.rect(temp_surface, (255, 255, 255), settings_ui['slider_handle_rect'])
    
    # Draw buttons
    pygame.draw.rect(temp_surface, (50, 150, 50), settings_ui['prime_rect'])
    pygame.draw.rect(temp_surface, (150, 50, 50), settings_ui['clean_rect'])
    
    # Draw switch background
    switch_color = (0, 200, 0) if INVERT_PUMP_PINS else (100, 100, 100)
    pygame.draw.rect(temp_surface, switch_color, settings_ui['switch_rect'])
    pygame.draw.rect(temp_surface, (200, 200, 200), settings_ui['switch_rect'], 2)
    
    # Draw switch indicator (circle)
    indicator_radius = 12
    if INVERT_PUMP_PINS:
        # ON position - indicator on the right
        indicator_x = settings_ui['switch_rect'].x + settings_ui['switch_rect'].width - indicator_radius - 3
    else:
        # OFF position - indicator on the left
        indicator_x = settings_ui['switch_rect'].x + indicator_radius + 3
    indicator_y = settings_ui['switch_rect'].y + settings_ui['switch_rect'].height // 2
    pygame.draw.circle(temp_surface, (255, 255, 255), (indicator_x, indicator_y), indicator_radius)
    
    add_layer(temp_surface, (0, 0), key='settings_controls')
    
    # Draw slider label
    add_layer(settings_ui['slider_label'], settings_ui['slider_label_rect'], key='slider_label')
    
    # Draw button text
    add_layer(settings_ui['prime_text'], settings_ui['prime_text_rect'], key='prime_text')
    add_layer(settings_ui['clean_text'], settings_ui['clean_text_rect'], key='clean_text')
    
    # Draw switch label
    add_layer(settings_ui['switch_label'], settings_ui['switch_label_rect'], key='switch_label')
    
    # Draw access info
    add_layer(settings_ui['access_label'], settings_ui['access_label_rect'], key='access_label')
    add_layer(settings_ui['ip_label'], settings_ui['ip_label_rect'], key='ip_label')

def create_settings_tab():
    """Create the small tab at the bottom for accessing settings"""
    tab_width = 80
    tab_height = 20
    tab_x = (screen_width - tab_width) // 2
    tab_y = screen_height - tab_height
    
    tab_rect = pygame.Rect(tab_x, tab_y, tab_width, tab_height)
    
    # Create simple tab surface
    tab_surface = pygame.Surface((tab_width, tab_height))
    tab_surface.fill((60, 60, 60))  # Dark gray
    
    # Add border for definition
    pygame.draw.rect(tab_surface, (120, 120, 120), (0, 0, tab_width, tab_height), 2)
    
    return {
        'rect': tab_rect,
        'surface': tab_surface,
        'base_y': tab_y,  # Store original position
        'width': tab_width,
        'height': tab_height
    }

def animate_settings_tray(settings_ui, settings_tab, show_tray, duration=300):
    """Animate the settings tray sliding up or down"""
    clock = pygame.time.Clock()
    start_time = pygame.time.get_ticks()
    tray_height = settings_ui['tray_rect'].height
    
    if show_tray:
        # Slide up from bottom
        start_y = screen_height
        end_y = screen_height - tray_height
    else:
        # Slide down to bottom
        start_y = screen_height - tray_height
        end_y = screen_height
    
    while True:
        elapsed = pygame.time.get_ticks() - start_time
        progress = min(elapsed / duration, 1.0)
        
        current_y = start_y + (end_y - start_y) * progress
        settings_ui['tray_rect'].y = current_y
        
        # No tab to update anymore
        
        # Update all related positions
        settings_ui['title_rect'].y = current_y + 40
        settings_ui['slider_bg_rect'].y = current_y + 100
        settings_ui['slider_handle_rect'].y = current_y + 95
        settings_ui['slider_label_rect'].y = current_y + 70
        settings_ui['prime_rect'].y = current_y + 180
        settings_ui['clean_rect'].y = current_y + 180
        settings_ui['prime_text_rect'].center = settings_ui['prime_rect'].center
        settings_ui['clean_text_rect'].center = settings_ui['clean_rect'].center
        settings_ui['switch_rect'].y = current_y + 250
        settings_ui['switch_label_rect'].y = current_y + 230
        settings_ui['access_label_rect'].y = current_y + 300
        settings_ui['ip_label_rect'].y = current_y + 325
        
        # Update tab layer
        # No tab layer to update anymore
        
        draw_settings_tray(settings_ui, True)
        draw_frame()
        
        if progress >= 1.0:
            break
        clock.tick(60)

def handle_settings_interaction(settings_ui, event_pos):
    """Handle interactions with settings tray elements"""
    # Check if slider is being dragged
    if settings_ui['slider_handle_rect'].collidepoint(event_pos):
        return 'slider_drag'
    
    # Check if prime button is clicked
    if settings_ui['prime_rect'].collidepoint(event_pos):
        return 'prime_pumps'
    
    # Check if clean button is clicked
    if settings_ui['clean_rect'].collidepoint(event_pos):
        return 'clean_pumps'
    
    # Check if switch is clicked
    if settings_ui['switch_rect'].collidepoint(event_pos):
        return 'toggle_switch'
    
    return None

def update_ml_coefficient(settings_ui, new_value):
    """Update the ML_COEFFICIENT setting and slider position"""
    global ML_COEFFICIENT
    
    # Convert from time per 50ml back to time per 1ml
    # new_value is seconds per 50ml, so ML_COEFFICIENT = new_value / 50
    ML_COEFFICIENT = max(0.1, min(1.0, new_value / 50))
    
    # Update slider handle position (convert back to 50ml for display)
    time_per_50ml = ML_COEFFICIENT * 50
    min_val_50ml, max_val_50ml = 5.0, 50.0
    slider_handle_x = settings_ui['slider_x'] + (time_per_50ml - min_val_50ml) / (max_val_50ml - min_val_50ml) * settings_ui['slider_width']
    settings_ui['slider_handle_rect'].x = slider_handle_x - 10
    
    # Update slider label
    slider_font = pygame.font.SysFont(None, 32)
    settings_ui['slider_label'] = slider_font.render(f"Time per 50ml: {time_per_50ml:.1f}s", True, (255, 255, 255))

def toggle_pump_direction():
    """Toggle the INVERT_PUMP_PINS setting"""
    global INVERT_PUMP_PINS
    INVERT_PUMP_PINS = not INVERT_PUMP_PINS
    logger.info(f'Pump direction inverted: {INVERT_PUMP_PINS}')

def create_drink_management_tray():
    """Create the drink management tray UI elements (Pumpen-Test)."""
    tray_height = int(screen_height * 0.6)
    tray_rect = pygame.Rect(0, -tray_height, screen_width, tray_height)

    overlay = pygame.Surface((screen_width, tray_height))
    overlay.set_alpha(220)
    for y in range(tray_height):
        color = (20, 25, 35)
        pygame.draw.line(overlay, color, (0, y), (screen_width, y))

    header_height = 70
    header_surface = pygame.Surface((screen_width, header_height))
    header_surface.set_alpha(180)
    header_surface.fill((25, 30, 40))

    title_font = pygame.font.SysFont('Arial', 28, bold=True)
    title_text = title_font.render("Pumpen-Test", True, (220, 220, 220))
    title_rect = title_text.get_rect(center=(screen_width // 2, header_height // 2))

    # Controls layout
    controls_y = header_height + 30
    section_gap = 80

    # Pump selection controls
    pump_label_font = pygame.font.SysFont('Arial', 22, bold=True)
    pump_label = pump_label_font.render("Pumpe", True, (220, 220, 220))
    pump_label_rect = pump_label.get_rect(center=(screen_width // 2, controls_y))

    pump_minus_rect = pygame.Rect(screen_width // 2 - 140, controls_y + 20, 50, 45)
    pump_plus_rect = pygame.Rect(screen_width // 2 + 90, controls_y + 20, 50, 45)
    pump_value_rect = pygame.Rect(screen_width // 2 - 70, controls_y + 20, 140, 45)

    # Duration controls
    dur_y = controls_y + section_gap
    dur_label_font = pygame.font.SysFont('Arial', 22, bold=True)
    dur_label = dur_label_font.render("Dauer (s)", True, (220, 220, 220))
    dur_label_rect = dur_label.get_rect(center=(screen_width // 2, dur_y))

    dur_minus_rect = pygame.Rect(screen_width // 2 - 140, dur_y + 20, 50, 45)
    dur_plus_rect = pygame.Rect(screen_width // 2 + 90, dur_y + 20, 50, 45)
    dur_value_rect = pygame.Rect(screen_width // 2 - 70, dur_y + 20, 140, 45)

    # Direction toggle
    dir_y = dur_y + section_gap
    dir_rect = pygame.Rect(screen_width // 2 - 70, dir_y, 140, 36)
    dir_label_small = pygame.font.SysFont('Arial', 18)
    dir_label_text = dir_label_small.render("Richtung: vorwärts", True, (220, 220, 220))
    dir_label_rect = dir_label_text.get_rect(center=(screen_width // 2, dir_y - 18))

    # Test button
    test_button_rect = pygame.Rect(screen_width // 2 - 120, dir_y + 60, 240, 55)
    test_font = pygame.font.SysFont('Arial', 24, bold=True)
    test_text = test_font.render("Pumpe testen", True, (255, 255, 255))
    test_text_rect = test_text.get_rect(center=test_button_rect.center)

    return {
        'tray_rect': tray_rect,
        'overlay': overlay,
        'header_surface': header_surface,
        'title_text': title_text,
        'title_rect': title_rect,
        'pump_minus_rect': pump_minus_rect,
        'pump_plus_rect': pump_plus_rect,
        'pump_value_rect': pump_value_rect,
        'pump_label': pump_label,
        'pump_label_rect': pump_label_rect,
        'dur_minus_rect': dur_minus_rect,
        'dur_plus_rect': dur_plus_rect,
        'dur_value_rect': dur_value_rect,
        'dur_label': dur_label,
        'dur_label_rect': dur_label_rect,
        'dir_rect': dir_rect,
        'dir_label_rect': dir_label_rect,
        'test_button_rect': test_button_rect,
        'test_text': test_text,
        'test_text_rect': test_text_rect,
        'selected_pump': 1,
        'duration_sec': 5.0,
        'reverse': False,
        'testing': False
    }

def create_drink_management_tab():
    """Create the small tab at the top for accessing drink management"""
    tab_width = 80
    tab_height = 20
    tab_x = (screen_width - tab_width) // 2
    tab_y = 0
    
    tab_rect = pygame.Rect(tab_x, tab_y, tab_width, tab_height)
    
    # Create simple tab surface
    tab_surface = pygame.Surface((tab_width, tab_height))
    tab_surface.fill((60, 60, 60))  # Dark gray
    
    # Add border for definition
    pygame.draw.rect(tab_surface, (120, 120, 120), (0, 0, tab_width, tab_height), 2)
    
    return {
        'rect': tab_rect,
        'surface': tab_surface,
        'base_y': tab_y,  # Store original position
        'width': tab_width,
        'height': tab_height
    }

def draw_drink_management_tray(drink_ui, is_visible, events=None):
    """Draw the pump test tray if visible"""
    if not is_visible:
        return

    add_layer(drink_ui['overlay'], drink_ui['tray_rect'], key='drink_overlay')

    header_rect = pygame.Rect(drink_ui['tray_rect'].x, drink_ui['tray_rect'].y,
                              drink_ui['tray_rect'].width, 70)
    add_layer(drink_ui['header_surface'], header_rect, key='drink_header')
    add_layer(drink_ui['title_text'], (int(screen_width // 2 - drink_ui['title_text'].get_width() // 2),
                                       int(drink_ui['tray_rect'].y + 20)), key='drink_title')

    # Temporary surface to draw controls
    temp_surface = pygame.Surface(screen_size, pygame.SRCALPHA)

    # Pump label
    temp_surface.blit(drink_ui['pump_label'], (int(drink_ui['pump_label_rect'].x),
                                               int(drink_ui['pump_label_rect'].y)))

    # Pump controls
    pygame.draw.rect(temp_surface, (70, 70, 70), drink_ui['pump_minus_rect'])
    pygame.draw.rect(temp_surface, (70, 70, 70), drink_ui['pump_plus_rect'])
    pygame.draw.rect(temp_surface, (40, 40, 40), drink_ui['pump_value_rect'])
    pygame.draw.rect(temp_surface, (200, 200, 200), drink_ui['pump_minus_rect'], 2)
    pygame.draw.rect(temp_surface, (200, 200, 200), drink_ui['pump_plus_rect'], 2)
    pygame.draw.rect(temp_surface, (200, 200, 200), drink_ui['pump_value_rect'], 2)

    minus_font = pygame.font.SysFont('Arial', 28, bold=True)
    plus_font = minus_font
    val_font = pygame.font.SysFont('Arial', 26, bold=True)
    minus_text = minus_font.render('-', True, (255, 255, 255))
    plus_text = plus_font.render('+', True, (255, 255, 255))
    pump_val_text = val_font.render(str(drink_ui['selected_pump']), True, (255, 255, 255))

    temp_surface.blit(minus_text, minus_text.get_rect(center=(int(drink_ui['pump_minus_rect'].centerx), int(drink_ui['pump_minus_rect'].centery))))
    temp_surface.blit(plus_text, plus_text.get_rect(center=(int(drink_ui['pump_plus_rect'].centerx), int(drink_ui['pump_plus_rect'].centery))))
    temp_surface.blit(pump_val_text, pump_val_text.get_rect(center=(int(drink_ui['pump_value_rect'].centerx), int(drink_ui['pump_value_rect'].centery))))

    # Duration controls
    # Duration label centered
    dur_label_pos = drink_ui['dur_label'].get_rect(center=(int(screen_width // 2), int(drink_ui['dur_label_rect'].y)))
    temp_surface.blit(drink_ui['dur_label'], dur_label_pos)

    pygame.draw.rect(temp_surface, (70, 70, 70), drink_ui['dur_minus_rect'])
    pygame.draw.rect(temp_surface, (70, 70, 70), drink_ui['dur_plus_rect'])
    pygame.draw.rect(temp_surface, (40, 40, 40), drink_ui['dur_value_rect'])
    pygame.draw.rect(temp_surface, (200, 200, 200), drink_ui['dur_minus_rect'], 2)
    pygame.draw.rect(temp_surface, (200, 200, 200), drink_ui['dur_plus_rect'], 2)
    pygame.draw.rect(temp_surface, (200, 200, 200), drink_ui['dur_value_rect'], 2)

    dur_val_text = val_font.render(f"{drink_ui['duration_sec']:.1f}", True, (255, 255, 255))
    temp_surface.blit(minus_text, minus_text.get_rect(center=(int(drink_ui['dur_minus_rect'].centerx), int(drink_ui['dur_minus_rect'].centery))))
    temp_surface.blit(plus_text, plus_text.get_rect(center=(int(drink_ui['dur_plus_rect'].centerx), int(drink_ui['dur_plus_rect'].centery))))
    temp_surface.blit(dur_val_text, dur_val_text.get_rect(center=(int(drink_ui['dur_value_rect'].centerx), int(drink_ui['dur_value_rect'].centery))))

    # Direction toggle
    pygame.draw.rect(temp_surface, (100, 100, 100), drink_ui['dir_rect'])
    pygame.draw.rect(temp_surface, (200, 200, 200), drink_ui['dir_rect'], 2)
    knob_x = int(drink_ui['dir_rect'].x + (drink_ui['dir_rect'].width - 18 - 4 if drink_ui['reverse'] else 4))
    knob_rect = pygame.Rect(knob_x, int(drink_ui['dir_rect'].y + 4), 18, int(drink_ui['dir_rect'].height - 8))
    pygame.draw.rect(temp_surface, (0, 200, 0) if not drink_ui['reverse'] else (200, 100, 100), knob_rect)
    dir_label_small = pygame.font.SysFont('Arial', 18)
    dir_text = "Richtung: rückwärts" if drink_ui['reverse'] else "Richtung: vorwärts"
    dir_text_surf = dir_label_small.render(dir_text, True, (220, 220, 220))
    dir_text_rect = dir_text_surf.get_rect(center=(int(screen_width // 2), int(drink_ui['dir_rect'].y - 18)))
    temp_surface.blit(dir_text_surf, dir_text_rect)

    # Test button
    pygame.draw.rect(temp_surface, (50, 150, 50) if not drink_ui['testing'] else (120, 120, 120), drink_ui['test_button_rect'])
    pygame.draw.rect(temp_surface, (200, 200, 200), drink_ui['test_button_rect'], 2)
    temp_surface.blit(drink_ui['test_text'], drink_ui['test_text_rect'])

    add_layer(temp_surface, (0, 0), key='pump_test_controls')

def _force_remove_pump_labels():
    """Entfernt explizit alle Pump-Labels die als Overlay hängen bleiben könnten"""
    # Entferne alle Pump-Labels von 1-12
    for i in range(1, 13):
        remove_layer(f'pump_label_{i}')

def animate_drink_management_tray(drink_ui, drink_tab, show_tray, duration=300):
    """Animate the pump test tray sliding down or up"""
    clock = pygame.time.Clock()
    start_time = pygame.time.get_ticks()
    tray_height = drink_ui['tray_rect'].height
    
    if show_tray:
        # Slide down from top
        start_y = -tray_height
        end_y = 0
    else:
        # Slide up to top
        start_y = 0
        end_y = -tray_height
    
    while True:
        elapsed = pygame.time.get_ticks() - start_time
        progress = min(elapsed / duration, 1.0)
        
        current_y = start_y + (end_y - start_y) * progress
        current_y_int = int(current_y)
        drink_ui['tray_rect'].y = current_y_int
        
        # No tab to update anymore
        
        # Update all related positions
        # Title position update removed
        
        # Dropdown positions are now static - no more flickering
        
        # Update control positions vertically
        # Pump controls
        dy = current_y_int + 30
        drink_ui['pump_label_rect'].y = int(dy)
        drink_ui['pump_minus_rect'].y = int(dy + 20)
        drink_ui['pump_plus_rect'].y = int(dy + 20)
        drink_ui['pump_value_rect'].y = int(dy + 20)

        # Duration controls
        dy2 = int(dy + 80)
        drink_ui['dur_label_rect'].y = int(dy2)
        drink_ui['dur_minus_rect'].y = int(dy2 + 20)
        drink_ui['dur_plus_rect'].y = int(dy2 + 20)
        drink_ui['dur_value_rect'].y = int(dy2 + 20)

        # Direction and button
        dy3 = int(dy2 + 80)
        drink_ui['dir_rect'].y = int(dy3)
        drink_ui['test_button_rect'].y = int(dy3 + 60)
        drink_ui['test_text_rect'].center = drink_ui['test_button_rect'].center
        
        # No tab layer to update anymore
        
        draw_drink_management_tray(drink_ui, True)
        draw_frame()
        
        if progress >= 1.0:
            break
        clock.tick(60)

def handle_drink_management_interaction(drink_ui, event, event_pos):
    """Handle interactions with pump test tray elements"""
    if event.type == pygame.MOUSEBUTTONDOWN:
        if drink_ui['pump_minus_rect'].collidepoint(event_pos):
            return 'pump_minus'
        if drink_ui['pump_plus_rect'].collidepoint(event_pos):
            return 'pump_plus'
        if drink_ui['dur_minus_rect'].collidepoint(event_pos):
            return 'dur_minus'
        if drink_ui['dur_plus_rect'].collidepoint(event_pos):
            return 'dur_plus'
        if drink_ui['dir_rect'].collidepoint(event_pos):
            return 'toggle_dir'
        if drink_ui['test_button_rect'].collidepoint(event_pos):
            return 'test_pump'
    return None

def update_dropdown_selection(dropdown, new_value):
    """Update dropdown selection and save to config"""
    dropdown['current_value'] = new_value
    
    # Save to pump config
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except:
        config = {}
    
    config[f"Pump {dropdown['pump_number']}"] = new_value
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def generate_new_drink_menu():
    """Generate a new drink menu using OpenAI"""
    import openai
    
    if not OPENAI_API_KEY:
        logger.error("OpenAI API key not found")
        return
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        prompt = """Create a comprehensive list of as many unique and interesting cocktail ingredients as possible. 
        Focus on spirits, liqueurs, juices, syrups, and mixers that would be commonly used in cocktails.
        Include both alcoholic and non-alcoholic ingredients.
        Make sure to include a wide variety of options for a well-stocked bar.
        Return only the list of ingredients, one per line, in alphabetical order."""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a cocktail expert. Provide comprehensive lists of cocktail ingredients."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000
        )
        
        # Parse the response and update drink options
        new_drinks = [""] + [line.strip() for line in response.choices[0].message.content.split('\n') if line.strip()]
        
        # Update drink_options.json
        with open('drink_options.json', 'w') as f:
            json.dump({"drinks": new_drinks}, f, indent=2)
        
        logger.info(f"Generated {len(new_drinks)-1} new drink options")
        return new_drinks
        
    except Exception as e:
        logger.error(f"Error generating drink menu: {e}")
        return None

def run_interface():

    def load_cocktail_image(cocktail):
        """Given a Cocktail object, load the image for that cocktail and scale it to the screen size"""
        if cocktail.get('is_qr_slide'):
            # For QR code slides, use the QR surface directly
            qr_surface = cocktail.get('qr_surface')
            if qr_surface:
                return pygame.transform.scale(qr_surface, (screen_width * COCKTAIL_IMAGE_SCALE, screen_height * COCKTAIL_IMAGE_SCALE))
            else:
                return None
        
        # Regular cocktail image loading
        path = get_cocktail_image_path(cocktail)
        try:
            img = pygame.image.load(path)
            img = pygame.transform.scale(img, (screen_width * COCKTAIL_IMAGE_SCALE, screen_height * COCKTAIL_IMAGE_SCALE))
            return img
        except Exception as e:
            logger.exception(f'Error loading {path}')
            return None

    def load_cocktail(index):
        """Load a cocktail based on a provided index. Also pre-load the images for the previous and next cocktails"""
        current_cocktail = cocktails[index]
        current_image = load_cocktail_image(current_cocktail)
        current_cocktail_name = current_cocktail.get('normal_name', '')
        previous_cocktail = cocktails[(index - 1) % len(cocktails)]
        previous_image = load_cocktail_image(previous_cocktail)
        next_cocktail = cocktails[(index + 1) % len(cocktails)]
        next_image = load_cocktail_image(next_cocktail)
        return current_cocktail, current_image, current_cocktail_name, previous_image, next_image

    # Load the static background image (tipsy.png)
    try:
        background = pygame.image.load('./tipsy.jpg')
        background = pygame.transform.scale(background, screen_size)
        add_layer(background, (0, 0), key='background')
    except Exception as e:
        logger.exception('Error loading background image (tipsy.png)')
        add_layer((0, 0), function=screen.fill, key='background')
    
    cocktails = get_cocktails_with_qr()
    
    if not cocktails:
        logger.critical('No valid cocktails found in cocktails.json')
        pygame.quit()
        return
    current_index = 0
    current_cocktail, current_image, current_cocktail_name, previous_image, next_image = load_cocktail(current_index)
    reload_time = pygame.time.get_ticks()

    margin = 50  # adjust as needed for spacing
    # Load single & double buttons and scale them to 75% of original (base size: 150x150)
    try:
        single_logo = pygame.image.load('single.png')
        single_logo = pygame.transform.scale(single_logo, (150, 150))
        single_rect = pygame.Rect(margin, (screen_height - 150) // 2, 150, 150)
        add_layer(single_logo, single_rect, key='single_logo')
    except Exception as e:
        logger.exception('Error loading single.png:')
        single_logo = None
    try:
        double_logo = pygame.image.load('double.png')
        double_logo = pygame.transform.scale(double_logo, (150, 150))
        double_rect = pygame.Rect(screen_width - margin - 150, (screen_height - 150) // 2, 150, 150)
        add_layer(double_logo, double_rect, key='double_logo')
    except Exception:
        logger.exception('Error loading double.png')
        double_logo = None
    # Favoriten- und Reload-Buttons werden jetzt im Drink Management Menü angezeigt
    favorite_rect = None
    favorite_logo = None
    unfavorite_logo = None
    reload_cocktails_rect = None
    reload_logo = None

    # Initialize settings tray (no tab needed)
    settings_ui = create_settings_tray()
    settings_visible = False
    slider_dragging = False
    
    # Initialize drink management tray (no tab needed)
    drink_ui = create_drink_management_tray()
    drink_visible = False
    dropdown_open = None
    generating_menu = False
    
    # Sicherheit: Entferne alle Pump-Labels beim Start
    _force_remove_pump_labels()

    dragging = False
    drag_start_x = 0
    drag_offset = 0
    clock = pygame.time.Clock()

    running = True
    last_refresh_check = pygame.time.get_ticks()
    refresh_check_interval = 1000  # Check every 1 second
    
    while running:
        # Check for refresh signals periodically
        current_time = pygame.time.get_ticks()
        if current_time - last_refresh_check > refresh_check_interval:
            if check_for_refresh_signal():
                logger.info("Refreshing cocktails due to app signal")
                cocktails = get_cocktails_with_qr()
                current_cocktail, current_image, current_cocktail_name, previous_image, next_image = load_cocktail(current_index)
            last_refresh_check = current_time
        
        events = pygame.event.get()
        for event in events:
            # Handle dropdown events globally if drink tray is visible
            if drink_visible:
                for dropdown in drink_ui['dropdowns']:
                    if dropdown['dropdown'].handle_event(event):
                        # Check if selection changed
                        new_value = dropdown['dropdown'].get_selected()
                        if new_value != dropdown['current_value']:
                            update_dropdown_selection(dropdown, new_value)
            
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                # Start tracking for potential swipe gestures
                swipe_start_pos = event.pos
                swipe_start_time = pygame.time.get_ticks()
                
                # Reset dragging state for clean gesture detection
                dragging = False
                drag_offset = 0
                
                # Check if drink management tray is clicked
                if drink_visible and drink_ui['tray_rect'].collidepoint(event.pos):
                    interaction = handle_drink_management_interaction(drink_ui, event, event.pos)
                    if interaction:
                        if interaction == 'pump_minus':
                            drink_ui['selected_pump'] = max(1, drink_ui['selected_pump'] - 1)
                        elif interaction == 'pump_plus':
                            drink_ui['selected_pump'] = min(12, drink_ui['selected_pump'] + 1)
                        elif interaction == 'dur_minus':
                            drink_ui['duration_sec'] = max(0.5, round(drink_ui['duration_sec'] - 0.5, 1))
                        elif interaction == 'dur_plus':
                            drink_ui['duration_sec'] = min(60.0, round(drink_ui['duration_sec'] + 0.5, 1))
                        elif interaction == 'toggle_dir':
                            drink_ui['reverse'] = not drink_ui['reverse']
                        elif interaction == 'test_pump' and not drink_ui['testing']:
                            # Run pump test in a thread to avoid UI blocking
                            import threading
                            def run_test():
                                try:
                                    drink_ui['testing'] = True
                                    from controller import setup_gpio, motor_forward, motor_reverse, motor_stop, MOTORS
                                    setup_gpio()
                                    pump_index = drink_ui['selected_pump'] - 1
                                    ia, ib = MOTORS[pump_index]
                                    if drink_ui['reverse']:
                                        motor_reverse(ia, ib)
                                    else:
                                        motor_forward(ia, ib)
                                    time.sleep(drink_ui['duration_sec'])
                                except Exception as e:
                                    logger.error(f"Pump test failed: {e}")
                                finally:
                                    try:
                                        motor_stop(ia, ib)
                                    except Exception:
                                        pass
                                    drink_ui['testing'] = False
                            threading.Thread(target=run_test, daemon=True).start()
                        continue
                
                # Check if settings tray is clicked
                if settings_visible and settings_ui['tray_rect'].collidepoint(event.pos):
                    interaction = handle_settings_interaction(settings_ui, event.pos)
                    if interaction == 'slider_drag':
                        slider_dragging = True
                    elif interaction == 'prime_pumps':
                        # Import and call prime_pumps function
                        from controller import prime_pumps
                        prime_pumps(duration=10)
                    elif interaction == 'clean_pumps':
                        # Import and call clean_pumps function
                        from controller import clean_pumps
                        clean_pumps(duration=10)
                    elif interaction == 'toggle_switch':
                        # Toggle pump direction
                        toggle_pump_direction()
                    continue
                
                # If drink management is visible and clicked outside, close it
                if drink_visible:
                    drink_visible = False
                    animate_drink_management_tray(drink_ui, None, drink_visible)
                    continue
                
                # If settings is visible and clicked outside, close it
                if settings_visible:
                    settings_visible = False
                    animate_settings_tray(settings_ui, None, settings_visible)
                    continue
                
                dragging = True
                drag_start_x = event.pos[0]
            if event.type == pygame.MOUSEMOTION:
                # Tab dragging no longer needed - using swipe gestures instead
                if slider_dragging:
                    # Update slider based on mouse position
                    mouse_x = event.pos[0]
                    slider_x = settings_ui['slider_x']
                    slider_width = settings_ui['slider_width']
                    
                    # Calculate new value (time per 50ml)
                    relative_x = max(0, min(slider_width, mouse_x - slider_x))
                    min_val_50ml, max_val_50ml = 5.0, 50.0
                    new_value = min_val_50ml + (relative_x / slider_width) * (max_val_50ml - min_val_50ml)
                    update_ml_coefficient(settings_ui, new_value)
                elif dragging:
                    current_x = event.pos[0]
                    drag_offset = current_x - drag_start_x
            if event.type == pygame.MOUSEBUTTONUP:
                # Check for swipe gestures
                if 'swipe_start_pos' in locals():
                    swipe_end_pos = event.pos
                    swipe_end_time = pygame.time.get_ticks()
                    
                    # Calculate swipe distance and direction
                    swipe_distance_x = swipe_end_pos[0] - swipe_start_pos[0]
                    swipe_distance_y = swipe_end_pos[1] - swipe_start_pos[1]
                    swipe_time = swipe_end_time - swipe_start_time
                    
                    # Only process swipes that are fast enough (within 500ms) and long enough (>100 pixels)
                    # Also check that vertical movement is significantly larger than horizontal movement
                    if (swipe_time < 500 and 
                        abs(swipe_distance_y) > 100 and 
                        abs(swipe_distance_y) > abs(swipe_distance_x) * 1.5):
                        # Check if swipe starts in the correct screen area
                        top_zone = screen_height * 0.1  # Oberstes 10% des Bildschirms
                        bottom_zone = screen_height * 0.9  # Unterstes 10% des Bildschirms
                        
                        if swipe_distance_y > 0:  # Swipe down (from top)
                            # Only open drink management if swipe starts in top 10% of screen
                            if swipe_start_pos[1] <= top_zone:
                                # Check if settings is already open - if so, close it first
                                if settings_visible:
                                    settings_visible = False
                                    animate_settings_tray(settings_ui, None, settings_visible)
                                
                                # Now open drink management menu (pulldown)
                                if not drink_visible:
                                    drink_visible = True
                                    animate_drink_management_tray(drink_ui, None, drink_visible)
                                else:
                                    # Close if already open
                                    drink_visible = False
                                    # Remove all pump labels when closing
                                    for dropdown in drink_ui['dropdowns']:
                                        remove_layer(f'pump_label_{dropdown["pump_number"]}')
                                    _force_remove_pump_labels()
                                    animate_drink_management_tray(drink_ui, None, drink_visible)
                        elif swipe_distance_y < 0:  # Swipe up (from bottom)
                            # Only open settings if swipe starts in bottom 10% of screen
                            if swipe_start_pos[1] >= bottom_zone:
                                # Check if drink management is already open - if so, close it first
                                if drink_visible:
                                    drink_visible = False
                                    # Remove all pump labels when closing
                                    for dropdown in drink_ui['dropdowns']:
                                        remove_layer(f'pump_label_{dropdown["pump_number"]}')
                                    _force_remove_pump_labels()
                                    animate_drink_management_tray(drink_ui, None, drink_visible)
                                
                                # Now open settings menu (pull-up)
                                if not settings_visible:
                                    settings_visible = True
                                    animate_settings_tray(settings_ui, None, settings_visible)
                                else:
                                    # Close if already open
                                    settings_visible = False
                                    animate_settings_tray(settings_ui, None, settings_visible)
                        continue
                    
                    # Clean up swipe tracking variables
                    del swipe_start_pos, swipe_start_time
                
                # If no vertical swipe was detected, check for horizontal swipes
                # This ensures horizontal swipes work even with slight vertical movement
                
                # Check if we should process horizontal swipes
                # Only process if we have a significant horizontal movement
                if 'swipe_start_pos' in locals():
                    swipe_distance_x = event.pos[0] - swipe_start_pos[0]
                    swipe_distance_y = event.pos[1] - swipe_start_pos[1]
                    
                    # If horizontal movement is dominant, allow horizontal swiping
                    if abs(swipe_distance_x) > abs(swipe_distance_y) * 1.2:
                        # Enable horizontal swiping by setting dragging state
                        if not dragging:
                            dragging = True
                            drag_start_x = swipe_start_pos[0]
                
                if slider_dragging:
                    slider_dragging = False
                    continue
                elif dragging:
                    # If it's a click (minimal drag), check extra logos.
                    if abs(drag_offset) < 10:
                        pos = event.pos
                        if single_rect.collidepoint(pos):
                            # Animate single logo click
                            if single_logo:
                                animate_logo_click(single_logo, single_rect, base_size=150, target_size=220, layer_key='single_logo', duration=150)

                            executor_watcher = make_drink(current_cocktail, 'single')

                            show_pouring_and_loading(watcher=executor_watcher)

                        elif double_rect.collidepoint(pos):
                            # Animate double logo click
                            if double_logo:
                                animate_logo_click(double_logo, double_rect, base_size=150, target_size=220, layer_key='double_logo', duration=150)

                            executor_watcher = make_drink(current_cocktail, 'double')

                            show_pouring_and_loading(executor_watcher)
                    
                        # Favoriten- und Reload-Buttons sind jetzt im Drink Management Menü
                            
                        dragging = False
                        drag_offset = 0
                        continue  # Skip further swipe handling.
                    # Otherwise, it's a swipe.
                    # Reduced threshold for more responsive horizontal swiping
                    if abs(drag_offset) > screen_width / 6:
                        if drag_offset < 0:
                            target_offset = -screen_width
                            new_index = (current_index + 1) % len(cocktails)
                        else:
                            target_offset = screen_width
                            new_index = (current_index - 1) % len(cocktails)
                        start_offset = drag_offset
                        duration = 200  # Faster animation for smoother feel
                        start_time = pygame.time.get_ticks()
                        while True:
                            elapsed = pygame.time.get_ticks() - start_time
                            progress = min(elapsed / duration, 1.0)
                            current_offset = start_offset + (target_offset - start_offset) * progress
                            add_layer(current_image, (current_offset + cocktail_image_offset, cocktail_image_offset), key='current_cocktail')
                            if drag_offset < 0:
                                add_layer(next_image, (screen_width + current_offset + cocktail_image_offset, cocktail_image_offset), key='next_cocktail')
                            else:
                                add_layer(previous_image, (-screen_width + current_offset + cocktail_image_offset, cocktail_image_offset), key='previous_cocktail')
                            draw_frame()
                            if progress >= 1.0:
                                break
                            clock.tick(120)  # Higher frame rate for smoother animation
                        current_index = new_index
                        current_cocktail, current_image, current_cocktail_name, previous_image, next_image = load_cocktail(current_index)

                        # Animate both extra logos zooming together.
                        if single_logo and double_logo:
                            animate_both_logos_zoom(single_logo, double_logo, single_rect, double_rect, base_size=150, target_size=175, duration=300)
                    else:
                        # Animate snapping back if swipe is insufficient.
                        start_offset = drag_offset
                        duration = 200  # Faster animation for smoother feel
                        start_time = pygame.time.get_ticks()
                        while True:
                            elapsed = pygame.time.get_ticks() - start_time
                            progress = min(elapsed / duration, 1.0)
                            current_offset = start_offset * (1 - progress)
                            add_layer(current_image, (current_offset + cocktail_image_offset, cocktail_image_offset), key='current_cocktail')
                            
                            # Intelligente Text-Anpassung für Cocktail-Namen (gleiche Logik wie oben)
                            if current_cocktail.get('is_qr_slide'):
                                # For QR code slide, show the URL
                                drink_name = current_cocktail.get('url', 'Scan QR Code')
                            else:
                                drink_name = current_cocktail_name
                            
                            # Prüfe Text-Länge und passe Schriftgröße an
                            max_text_width = screen_width * 0.8  # 80% der Bildschirmbreite
                            font_size = normal_text_size
                            
                            # Reduziere Schriftgröße schrittweise bis der Text passt
                            while font_size > 24:  # Minimale Schriftgröße
                                font = pygame.font.SysFont(None, font_size)
                                text_surface = font.render(drink_name, True, (255, 255, 255))
                                if text_surface.get_width() <= max_text_width:
                                    break
                                font_size -= 8
                            
                            # Wenn der Text immer noch zu lang ist, verwende Text-Wrapping
                            if text_surface.get_width() > max_text_width:
                                font = pygame.font.SysFont(None, font_size)
                                wrapped_lines = wrap_text(drink_name, font, max_text_width)
                                
                                # Zeichne jede Zeile separat
                                line_height = font.get_height() + 5
                                total_height = len(wrapped_lines) * line_height
                                start_y = text_position[1] - total_height // 2
                                
                                for i, line in enumerate(wrapped_lines):
                                    line_surface = font.render(line, True, (255, 255, 255))
                                    line_rect = line_surface.get_rect(center=(text_position[0], start_y + i * line_height))
                                    add_layer(line_surface, line_rect, key=f'cocktail_name_line_{i}')
                            else:
                                # Normaler Fall: Text passt in eine Zeile
                                text_rect = text_surface.get_rect(center=text_position)
                                add_layer(text_surface, text_rect, key='cocktail_name')
                            
                            draw_frame()
                            if progress >= 1.0:
                                break
                            clock.tick(120)  # Higher frame rate for smoother animation
                    dragging = False
                    drag_offset = 0

        # Main drawing (when not in special animation)
        if RELOAD_COCKTAILS_TIMEOUT and pygame.time.get_ticks() - reload_time > RELOAD_COCKTAILS_TIMEOUT:
            logger.debug('Reloading cocktails due to auto reload timeout')
            cocktails = get_cocktails_with_qr()
            current_cocktail, current_image, current_cocktail_name, previous_image, next_image = load_cocktail(current_index)
            reload_time = pygame.time.get_ticks()

        if dragging:
            remove_layer('cocktail_name')
            remove_layer('favorite_logo')
            add_layer(current_image, (drag_offset + cocktail_image_offset, cocktail_image_offset), key='current_cocktail')
            if drag_offset < 0:
                add_layer(next_image, (screen_width + drag_offset + cocktail_image_offset, cocktail_image_offset), key='next_cocktail')
            elif drag_offset > 0:
                add_layer(previous_image, (-screen_width + drag_offset + cocktail_image_offset, cocktail_image_offset), key='previous_cocktail')
        else:
            remove_layer('next_cocktail')
            remove_layer('previous_cocktail')
            add_layer(current_image, (cocktail_image_offset, cocktail_image_offset), key='current_cocktail')
            
            # Entferne alle alten Text-Layer
            remove_layer('cocktail_name')
            for i in range(10):  # Entferne bis zu 10 Zeilen
                remove_layer(f'cocktail_name_line_{i}')
            
            # Intelligente Text-Anpassung für Cocktail-Namen
            if current_cocktail.get('is_qr_slide'):
                # For QR code slide, show the URL
                drink_name = current_cocktail.get('url', 'Scan QR Code')
            else:
                drink_name = current_cocktail_name
            
            # Prüfe Text-Länge und passe Schriftgröße an
            max_text_width = screen_width * 0.8  # 80% der Bildschirmbreite
            font_size = normal_text_size
            
            # Reduziere Schriftgröße schrittweise bis der Text passt
            while font_size > 24:  # Minimale Schriftgröße
                font = pygame.font.SysFont(None, font_size)
                text_surface = font.render(drink_name, True, (255, 255, 255))
                if text_surface.get_width() <= max_text_width:
                    break
                font_size -= 8
            
            # Wenn der Text immer noch zu lang ist, verwende Text-Wrapping
            if text_surface.get_width() > max_text_width:
                font = pygame.font.SysFont(None, font_size)
                wrapped_lines = wrap_text(drink_name, font, max_text_width)
                
                # Zeichne jede Zeile separat
                line_height = font.get_height() + 5
                total_height = len(wrapped_lines) * line_height
                start_y = text_position[1] - total_height // 2
                
                for i, line in enumerate(wrapped_lines):
                    line_surface = font.render(line, True, (255, 255, 255))
                    line_rect = line_surface.get_rect(center=(text_position[0], start_y + i * line_height))
                    add_layer(line_surface, line_rect, key=f'cocktail_name_line_{i}')
            else:
                # Normaler Fall: Text passt in eine Zeile
                text_rect = text_surface.get_rect(center=text_position)
                add_layer(text_surface, text_rect, key='cocktail_name')
            if ALLOW_FAVORITES:
                if current_cocktail.get('favorite', False) and favorite_logo:
                    add_layer(favorite_logo, favorite_rect, key='favorite_logo')
                elif unfavorite_logo:
                    add_layer(unfavorite_logo, favorite_rect, key='favorite_logo')
        
        # No tab positioning needed anymore
        
        # Draw pump test tray if visible
        if drink_visible:
            draw_drink_management_tray(drink_ui, True, events)
        else:
            draw_drink_management_tray(drink_ui, False, events)
        
        # Draw settings tray if visible
        if settings_visible:
            draw_settings_tray(settings_ui, True)
        
        draw_frame()
        
        # No dropdowns in pump test tray
        
        clock.tick(120)  # Higher frame rate for smoother interface
    pygame.quit()

if __name__ == '__main__':
    run_interface()
