# aiogram3-form
A library to create forms in aiogram3

```shell
pip install aiogram3-form
```

# Example
```Python
import asyncio

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram3_form import Form, FormField
from aiogram.fsm.context import FSMContext

bot = Bot(token=YOUR_TOKEN)
dispatcher = Dispatcher()
router = Router()
dispatcher.include_router(router)


class NameForm(Form, router=router):
    first_name: str = FormField(enter_message_text="Enter your first name please")
    second_name: str = FormField(
        enter_message_text="Enter your second name please",
        filter=F.text.len() > 10 & F.text,
    )
    age: int = FormField(
        enter_message_text="Enter age as integer",
        error_message_text="Age should be numeric!",
    )


@NameForm.submit()
async def name_form_submit_handler(form: NameForm, event_chat: types.Chat):
    # handle form data
    # also supports aiogram standart DI (e. g. middlewares, filters, etc)
    await form.answer(
        f"{form.first_name} {form.second_name} of age {form.age} in chat {event_chat.title}"
    )


@router.message(F.text == "/form")
async def form_handler(_, state: FSMContext):
    await NameForm.start(bot, state)  # start your form


async def main():
    await dispatcher.start_polling(bot)


asyncio.run(main())
```
