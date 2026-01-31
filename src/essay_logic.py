from typing import List, Optional, Any
from src.manager import ProviderManager
from src.essay_data import MaterialBank, EssayBank, EssayItem, EssaySession
import asyncio

class EssayGenerator:
    def __init__(self, manager: ProviderManager, m_bank: MaterialBank, e_bank: EssayBank, session: EssaySession):
        self.manager = manager
        self.m_bank = m_bank
        self.e_bank = e_bank
        self.session = session

    async def _ensure_uploads_for_provider(self, provider: Any) -> List[Any]:
        """Uploads files to a specific provider if not already present."""
        p_name = f"{provider.provider_name}_{provider.model_name}"
        handles = []
        
        for item in self.m_bank.items:
            handle = item.file_handles.get(p_name)
            if not handle:
                try:
                    handle = await provider.upload_file(item.path)
                    item.file_handles[p_name] = handle
                except Exception:
                    # If one fails, we continue; the model might still work without some files
                    # or fail later during generation which is better than hard crash here.
                    continue
            if handle:
                handles.append(handle)
        return handles

    def _build_system_prompt(self) -> str:
        prompt = "You are an expert essay writer. Answer the specific question below using the provided context files.\n\n"
        
        if self.e_bank.examples:
            prompt += "Style Examples (Mimic the tone, length, and structure of these):\n"
            for ex in self.e_bank.examples:
                prompt += f"Q: {ex.question}\nA: {ex.answer}\n---\n"
            prompt += "\n"
            
        return prompt

    async def run(self, item: EssayItem, on_update=None):
        """Runs the generation process using fallback system."""
        
        def local_update(msg):
            item.status = msg
            # Only save to disk for 'major' status changes, not every tick of a countdown
            if not msg or not msg.startswith("Rate limited"):
                self.session.save()
            if on_update: on_update(msg)

        async def generate_task(provider: Any, on_update=None):
            # 1. Upload for THIS provider
            if on_update: on_update("Uploading...")
            files = await self._ensure_uploads_for_provider(provider)
            
            # 2. Generate
            if on_update: on_update("Generating...")
            system_prompt = self._build_system_prompt()
            full_prompt = f"{system_prompt}\n\nQuestion: {item.question}\nAnswer:"
            
            return await provider.generate_essay(full_prompt, files)

        try:
            item.status = "Starting..."
            if on_update: on_update()

            essay = await self.manager.execute_with_fallback(
                'generate_essay_wrapper',
                generate_task,
                on_update=local_update
            )
            
            item.answer = essay
            item.status = "Done"
            self.session.save()
            if on_update: on_update()
            
        except Exception as e:
            item.status = f"Error: {str(e)}"
            item.answer = None
            self.session.save()
            if on_update: on_update()

    # We need a small hack or update to ProviderManager to support 
    # complex multi-step tasks like "Upload + Generate" as a single unit or
    # just pass the logic as a callback.
    # I'll update ProviderManager to be more flexible.
