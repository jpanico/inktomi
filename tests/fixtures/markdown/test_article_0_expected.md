# Test Article 0

> [!NOTE]
> **THIS PAGE IS USED FOR TESTING [GUFFIN](https://github.com/jpanico/guffin) – DO NOT REMOVE**
>
> A baseline Roam document, with almost no features
>
> Features:
>
> - 3 top-level blocks
> - nested blocks
> - italics text
> - bold text
> - this INFO `Callout box`, which contains Roam `page references`

block 1

- This para features *italics*

- This para features **bold**

- This para features ~~strikethrough~~

- This para features <mark>highlight</mark>

- This para features `inline-code`

- This para features includes a fenced code block:

  ``` python
  def fizz_buzz(limit: int = 100):
      for i in range(1, limit + 1):
          if i % 15 == 0:
              print("FizzBuzz")
          elif i % 3 == 0:
              print("Fizz")
          elif i % 5 == 0:
              print("Buzz")
          else:
              print(i)
  ```

- The child of this block is an isolated fenced code block
  ``` python
  def fizz_buzz(limit: int = 100):
      for i in range(1, limit + 1):
          if i % 15 == 0:
              print("FizzBuzz")
          elif i % 3 == 0:
              print("Fizz")
          elif i % 5 == 0:
              print("Buzz")
          else:
              print(i)
  ```

> This is a Markdown standard single line Block Quote

> This is a Markdown standard multi-line Block Quote
>
> this is the 2nd line
>
> - this is the 3rd line

- block 1.1
  - block 1.1.1
- block 1.2

block 2

block 3

- block 3.1
  - block 3.1.1
- block 3.2
